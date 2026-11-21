from __future__ import annotations

import argparse
import json
import secrets
import socket
import string
import struct
import threading
from dataclasses import dataclass, field
from typing import Callable

from main import MinesweeperGame, Player


CHUNK_SIZE = 1024
MAX_FRAME_SIZE = 256 * 1024
ROOM_CODE_LENGTH = 6


def send_packet(connection: socket.socket, message: dict) -> None:
	payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
	if len(payload) > MAX_FRAME_SIZE:
		raise ValueError("Message is larger than the allowed frame size.")
	frame = struct.pack("!I", len(payload)) + payload
	for offset in range(0, len(frame), CHUNK_SIZE):
		connection.sendall(frame[offset : offset + CHUNK_SIZE])


def receive_packet(connection: socket.socket) -> dict:
	header = _receive_exact(connection, 4)
	length = struct.unpack("!I", header)[0]
	if not 0 < length <= MAX_FRAME_SIZE:
		raise ValueError("Invalid message size.")
	payload = _receive_exact(connection, length)
	message = json.loads(payload.decode("utf-8"))
	if not isinstance(message, dict):
		raise ValueError("Message must be a JSON object.")
	return message


def _receive_exact(connection: socket.socket, length: int) -> bytes:
	data = bytearray()
	while len(data) < length:
		chunk = connection.recv(min(CHUNK_SIZE, length - len(data)))
		if not chunk:
			raise ConnectionError("The other side closed the connection.")
		data.extend(chunk)
	return bytes(data)


@dataclass
class Room:
	code: str
	game: MinesweeperGame
	sessions: dict[socket.socket, int] = field(default_factory=dict)


class RoomServer:
	def __init__(self, host: str = "0.0.0.0", port: int = 4444):
		self.host = host
		self.port = port
		self.rooms: dict[str, Room] = {}
		self._lock = threading.RLock()
		self._server_socket: socket.socket | None = None
		self._stopping = threading.Event()
		self._ready = threading.Event()
		self._startup_error: OSError | None = None
		self._thread: threading.Thread | None = None

	def start(self) -> int:
		if self._thread is not None and self._thread.is_alive():
			if self._startup_error is not None:
				raise self._startup_error
			return self.port
		self._ready.clear()
		self._startup_error = None
		self._stopping.clear()
		self._thread = threading.Thread(target=self.serve_forever, daemon=True)
		self._thread.start()
		if not self._ready.wait(5):
			raise TimeoutError("Online server did not start in time.")
		if self._startup_error is not None:
			raise self._startup_error
		return self.port

	def serve_forever(self) -> None:
		server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			server.bind((self.host, self.port))
			server.listen(32)
		except OSError as error:
			self._startup_error = error
			self._ready.set()
			server.close()
			return
		self._server_socket = server
		self.port = server.getsockname()[1]
		print(f"Saper Arena server listening on {self.host}:{self.port}", flush=True)
		self._ready.set()
		try:
			while not self._stopping.is_set():
				try:
					connection, _address = server.accept()
				except OSError:
					if self._stopping.is_set():
						break
					raise
				connection.settimeout(60)
				threading.Thread(target=self._serve_client, args=(connection,), daemon=True).start()
		finally:
			server.close()

	def stop(self) -> None:
		self._stopping.set()
		if self._server_socket is not None:
			self._server_socket.close()

	def _serve_client(self, connection: socket.socket) -> None:
		room: Room | None = None
		player_index: int | None = None
		try:
			request = receive_packet(connection)
			room, player_index = self._join_room(connection, request)
			send_packet(connection, {"type": "joined", "room": room.code, "player_index": player_index})
			self._broadcast(room)
			while True:
				request = receive_packet(connection)
				self._apply_action(room, connection, player_index, request)
		except (ConnectionError, OSError, ValueError, json.JSONDecodeError) as error:
			if isinstance(error, ValueError) and room is None:
				self._send_error(connection, str(error), fatal=True)
			elif room is not None and not self._stopping.is_set():
				self._send_error(connection, str(error), fatal=True)
		finally:
			if room is not None and player_index is not None:
				self._drop_session(room, connection, player_index)
			try:
				connection.close()
			except OSError:
				pass

	def _join_room(self, connection: socket.socket, request: dict) -> tuple[Room, int]:
		action = request.get("type")
		name = self._clean_name(request.get("name"))
		with self._lock:
			if action == "create":
				rows = self._integer_setting(request, "rows", 8, 48)
				columns = self._integer_setting(request, "columns", 8, 48)
				mine_count = self._integer_setting(request, "mine_count", 1, rows * columns - 1)
				code = self._new_room_code()
				game = MinesweeperGame(rows, columns, mine_count, [name])
				room = Room(code, game)
				self.rooms[code] = room
				player_index = 0
			elif action == "join":
				code = str(request.get("room", "")).strip().upper()
				if len(code) != ROOM_CODE_LENGTH or any(char not in string.ascii_uppercase + string.digits for char in code):
					raise ValueError("Room code must contain six letters or digits.")
				room = self.rooms.get(code)
				if room is None or room.game.finished:
					raise ValueError("Room not found or game has already ended.")
				if len(room.game.players) >= 4:
					raise ValueError("This room already has four players.")
				room.game.players.append(Player(name))
				player_index = len(room.game.players) - 1
			else:
				raise ValueError("First packet must be a create or join request.")
			room.sessions[connection] = player_index
			return room, player_index

	def _apply_action(self, room: Room, connection: socket.socket, player_index: int, request: dict) -> None:
		with self._lock:
			game = room.game
			if connection not in room.sessions or game.finished:
				return
			if player_index != game.current_player or game.players[player_index].lives <= 0:
				self._send_error(connection, "It is not your turn.")
				return
			action = request.get("type")
			try:
				row = int(request.get("row"))
				column = int(request.get("column"))
			except (TypeError, ValueError):
				self._send_error(connection, "Cell coordinates must be integers.")
				return
			if not (0 <= row < game.rows and 0 <= column < game.columns):
				self._send_error(connection, "Cell is outside the board.")
				return
			if action == "reveal":
				game.reveal(row, column)
			elif action == "flag":
				game.toggle_flag(row, column)
			else:
				self._send_error(connection, "Unknown move.")
				return
		self._broadcast(room)

	def _drop_session(self, room: Room, connection: socket.socket, player_index: int) -> None:
		with self._lock:
			room.sessions.pop(connection, None)
			if player_index < len(room.game.players) and room.game.players[player_index].lives > 0:
				room.game.players[player_index].lives = 0
				if room.game.current_player == player_index:
					room.game._advance_player()
				if all(player.lives <= 0 for player in room.game.players):
					room.game.finished = True
					room.game.won = False
			if not room.sessions:
				self.rooms.pop(room.code, None)
				return
		self._broadcast(room)

	def _broadcast(self, room: Room) -> None:
		with self._lock:
			sessions = list(room.sessions)
			state = self._game_state(room)
		for connection in sessions:
			try:
				send_packet(connection, {"type": "state", "state": state})
			except (OSError, ValueError):
				pass

	def _game_state(self, room: Room) -> dict:
		game = room.game
		visible_mines = game.mines if game.finished else game.opened.intersection(game.mines)
		return {
			"room": room.code,
			"rows": game.rows,
			"columns": game.columns,
			"mine_count": game.mine_count,
			"started": game.started,
			"finished": game.finished,
			"won": game.won,
			"current_player": game.current_player,
			"players": [
				{"name": player.name, "score": player.score, "lives": max(0, player.lives)}
				for player in game.players
			],
			"opened": [list(cell) for cell in game.opened],
			"flags": [list(cell) for cell in game.flags],
			"mines": [list(cell) for cell in visible_mines],
			"numbers": [
				[row, column, game.number_at(row, column)]
				for row, column in game.opened
				if (row, column) not in game.mines
			],
			"exploded": list(game.exploded) if game.exploded else None,
		}

	def _new_room_code(self) -> str:
		alphabet = string.ascii_uppercase + string.digits
		while True:
			code = "".join(secrets.choice(alphabet) for _ in range(ROOM_CODE_LENGTH))
			if code not in self.rooms:
				return code

	@staticmethod
	def _clean_name(value) -> str:
		name = " ".join(str(value or "").split())[:20]
		if not name:
			raise ValueError("Enter a player name.")
		return name

	@staticmethod
	def _integer_setting(request: dict, key: str, minimum: int, maximum: int) -> int:
		try:
			value = int(request.get(key))
		except (TypeError, ValueError) as error:
			raise ValueError(f"{key} must be an integer.") from error
		if not minimum <= value <= maximum:
			raise ValueError(f"{key} must be between {minimum} and {maximum}.")
		return value

	@staticmethod
	def _send_error(connection: socket.socket, text: str, fatal: bool = False) -> None:
		try:
			send_packet(connection, {"type": "error", "message": text, "fatal": fatal})
		except (OSError, ValueError):
			pass


class OnlineClient:
	def __init__(
		self,
		on_state: Callable[[dict], None],
		on_joined: Callable[[str, int], None],
		on_error: Callable[[str, bool], None],
	):
		self.on_state = on_state
		self.on_joined = on_joined
		self.on_error = on_error
		self._socket: socket.socket | None = None
		self._send_lock = threading.Lock()
		self._closed = threading.Event()

	def connect(self, host: str, port: int, request: dict) -> None:
		threading.Thread(target=self._connect_and_listen, args=(host, port, request), daemon=True).start()

	def _connect_and_listen(self, host: str, port: int, request: dict) -> None:
		try:
			connection = socket.create_connection((host, port), timeout=12)
			connection.settimeout(None)
			self._socket = connection
			send_packet(connection, request)
			while not self._closed.is_set():
				message = receive_packet(connection)
				kind = message.get("type")
				if kind == "joined":
					self.on_joined(str(message.get("room", "")), int(message.get("player_index", 0)))
				elif kind == "state":
					state = message.get("state")
					if isinstance(state, dict):
						self.on_state(state)
				elif kind == "error":
					fatal = bool(message.get("fatal", False))
					self.on_error(str(message.get("message", "Online server error.")), fatal)
					if fatal:
						self._closed.set()
						break
		except (OSError, ValueError, json.JSONDecodeError) as error:
			if not self._closed.is_set():
				self.on_error(str(error), True)
		finally:
			connection = self._socket
			self._socket = None
			if connection is not None:
				try:
					connection.close()
				except OSError:
					pass

	def send_action(self, action: str, row: int, column: int) -> None:
		connection = self._socket
		if connection is None or self._closed.is_set():
			self.on_error("Not connected to an online room.", True)
			return
		try:
			with self._send_lock:
				send_packet(connection, {"type": action, "row": row, "column": column})
		except (OSError, ValueError) as error:
			self.on_error(str(error), True)

	def close(self) -> None:
		self._closed.set()
		connection = self._socket
		if connection is not None:
			try:
				connection.shutdown(socket.SHUT_RDWR)
			except OSError:
				pass
			try:
				connection.close()
			except OSError:
				pass


def run_server(host: str = "0.0.0.0", port: int = 4444) -> None:
	RoomServer(host, port).serve_forever()


def main() -> None:
	parser = argparse.ArgumentParser(description="Saper Arena online room server")
	parser.add_argument("--host", default="0.0.0.0")
	parser.add_argument("--port", type=int, default=4444)
	arguments = parser.parse_args()
	run_server(arguments.host, arguments.port)


if __name__ == "__main__":
	main()
