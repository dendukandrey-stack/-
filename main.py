from __future__ import annotations

import random
from dataclasses import dataclass


PRESETS = (
	("Мини", 8, 10),
	("Лёгкая", 12, 24),
	("Средняя", 16, 40),
	("Большая", 24, 90),
	("Сложная", 32, 160),
	("Эксперт", 48, 360),
)


@dataclass
class Player:
	name: str
	score: int = 0
	lives: int = 3


class MinesweeperGame:
	def __init__(self, rows: int, columns: int, mine_count: int, names: list[str]):
		if not 8 <= rows <= 48 or not 8 <= columns <= 48:
			raise ValueError("Размер поля должен быть от 8 до 48 клеток.")
		if not 1 <= mine_count < rows * columns:
			raise ValueError("Число мин должно быть меньше размера поля.")
		if not 1 <= len(names) <= 4:
			raise ValueError("В игре может быть от одного до четырёх игроков.")

		self.rows = rows
		self.columns = columns
		self.mine_count = mine_count
		self.players = [Player(name or f"Игрок {index + 1}") for index, name in enumerate(names)]
		self.current_player = 0
		self.mines: set[tuple[int, int]] = set()
		self.opened: set[tuple[int, int]] = set()
		self.flags: set[tuple[int, int]] = set()
		self.started = False
		self.finished = False
		self.won = False
		self.exploded: tuple[int, int] | None = None

	@property
	def multiplayer(self) -> bool:
		return len(self.players) > 1

	@property
	def remaining_mines(self) -> int:
		return self.mine_count - len(self.flags)

	@property
	def current(self) -> Player:
		return self.players[self.current_player]

	def number_at(self, row: int, column: int) -> int:
		return sum(
			(near_row, near_column) in self.mines
			for near_row, near_column in self.neighbors(row, column)
		)

	def neighbors(self, row: int, column: int):
		for near_row in range(max(0, row - 1), min(self.rows, row + 2)):
			for near_column in range(max(0, column - 1), min(self.columns, column + 2)):
				if (near_row, near_column) != (row, column):
					yield near_row, near_column

	def toggle_flag(self, row: int, column: int) -> bool:
		cell = (row, column)
		if self.finished or cell in self.opened:
			return False
		if cell in self.flags:
			self.flags.remove(cell)
			return True
		if len(self.flags) >= self.mine_count:
			return False
		self.flags.add(cell)
		return True

	def reveal(self, row: int, column: int) -> str:
		cell = (row, column)
		if self.finished or cell in self.opened or cell in self.flags:
			return "ignored"

		if not self.started:
			all_cells = [
				(board_row, board_column)
				for board_row in range(self.rows)
				for board_column in range(self.columns)
				if (board_row, board_column) != cell
			]
			self.mines = set(random.sample(all_cells, self.mine_count))
			self.started = True

		if cell in self.mines:
			self.opened.add(cell)
			self.exploded = cell
			if not self.multiplayer:
				self.finished = True
				self.won = False
				return "lost"

			self.current.lives -= 1
			self.current.score = max(0, self.current.score - 2)
			if all(player.lives <= 0 for player in self.players):
				self.finished = True
				self.won = False
				return "lost"
			self._advance_player()
			return "mine"

		newly_opened = self._open_region(row, column)
		self.current.score += len(newly_opened)
		if len(self.opened - self.mines) >= self.rows * self.columns - self.mine_count:
			self.finished = True
			self.won = True
			return "won"
		if self.multiplayer:
			self._advance_player()
		return "safe"

	def _open_region(self, row: int, column: int) -> set[tuple[int, int]]:
		pending = [(row, column)]
		newly_opened: set[tuple[int, int]] = set()
		while pending:
			cell = pending.pop()
			if cell in self.opened or cell in self.flags or cell in self.mines:
				continue
			self.opened.add(cell)
			newly_opened.add(cell)
			if self.number_at(*cell) == 0:
				pending.extend(self.neighbors(*cell))
		return newly_opened

	def _advance_player(self) -> None:
		for offset in range(1, len(self.players) + 1):
			next_index = (self.current_player + offset) % len(self.players)
			if self.players[next_index].lives > 0:
				self.current_player = next_index
				return


def main() -> None:
	from ui import MinesweeperApp

	MinesweeperApp().run()


if __name__ == "__main__":
	main()
