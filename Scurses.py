#!/usr/bin/python3
# Scurses

from __future__ import annotations

import curses, curses.ascii, curses.textpad
from utils import *; logstart('Scurses')

MOUSE_WHEEL = (curses.BUTTON4_PRESSED | +2097152) #curses.REPORT_MOUSE_POSITION |

class SCWindow(TypeInit):
	# public:
	stdscr: '# curses.window'
	app: '# SCApp'
	key_handlers: dict[callable]
	views: list[SCView]
	inited: bool
	died: bool

	# private:
	waitrelease: '# SCKey | None'
	waitrelease_pressed: bool
	waitrelease_lastpressed: int
	debugstr: str

	# properties:
	top: SCView
	touched: bool

	def __init__(self, stdscr=None, app=None):
		self.stdscr, self.app = stdscr, app
		self.waitrelease = None

	def __del__(self):
		try: self.die()
		except AttributeError: pass

	def init(self):
		self.stdscr.nodelay(True)

		for view in self.views:
			view.init()

		self.inited = True
		self.touch()

	def die(self) -> bool -- ret:
		if (self.died): return True  # exactly in that order
		self.died = True
		for view in self.views:
			view.die()

	def addView(self, view: SCView):
		view.app = (self.app or self)
		self.views.append(view)
		if (self.inited): view.init()

	def popView(self):
		self.top.die()
		del self.top
		self.touch()

	def debugOut(self, *s, sep=' '):
		if (s): self.debugstr = S(sep.join(map(str, s))).wrap(self.stdscr.getmaxyx()[1]//2).split('\n')
		else: self.debugstr = ''

	def proc(self) -> bool -- ret:
		""" Process before `.draw()', e.g. check some condition to call `.touch()'.
		You should not use `.stdscr' here.
		You may use `.touched' meant for the upcoming frame here.
		Return: (ret)
			ret: stop recursive subclass processing.
		"""

		touch_next = bool()
		for view in self.views[::-1]:
			if (view.died):
				try: self.views.remove(view)
				except ValueError: pass
				else: touch_next = True
				continue
			if (touch_next): view.touch()
			view.proc()
			touch_next = (view.transparent and view.touched)

	def draw(self) -> bool -- ret:
		height, width = self.stdscr.getmaxyx()

		for ii, view in enumerate(self.views):
			view.draw(self.stdscr)

		if (self.debugstr):
			for ii, i in enumerate(self.debugstr):
				if (ii >= height): break
				self.stdscr.addstr(ii, (width - len(i))//2-1, i, curses.A_STANDOUT)

	def touch(self):
		if (self.views): self.top.touch()

	def touchAll(self):
		self.touch()
		for view in self.views:
			view.touch()

	def key(self, c: SCKey) -> bool -- ret:
		if (not c): return
		if (self.waitrelease):
			if (c != self.waitrelease or time.time()-self.waitrelease_lastpressed > 0.05): self.waitrelease = None
			else: self.waitrelease_lastpressed = time.time(); return

		self.debugOut()

		for view in self.views[::-1]:
			if (c == curses.KEY_RESIZE): view.touch()
			r = view.key(c)
			if (r): return r
		else:
			if (c in self.key_handlers): return self.key_handlers[c](self, c)
			elif (... in self.key_handlers): return self.key_handlers[...](self, c)

	def onkey(self, c):
		if (callable(c)): return self.onkey(c.__name__)(c)
		return lambda f: (self.key_handlers.__setitem__(SCKey(c), f) or f)

	def onkeyunknown(self, f):
		self.key_handlers[...] = f

	def waitkeyrelease(self, c):
		self.waitrelease = SCKey(c)
		self.waitrelease_pressed = False
		self.waitrelease_lastpressed = time.time()

	def loop(self, *rargs):
		self.draw()
		self.stdscr.noutrefresh(*rargs)

	@property
	def top(self) -> SCView:
		return self.views[-1]

	@top.deleter
	def top(self):
		del self.views[-1]

	@property
	def touched(self) -> bool:
		for view in reversed(self.views):
			if (view.touched): return True
		return False

class SCApp(SCWindow):
	# public:
	frame_delay: float
	proc_delay: int
	esc_delay: int
	mouse_delay: int
	mouse_mask: int

	# private:
	lastframe: int

	def __init__(self, *args, frame_rate=60, proc_rate=60, esc_delay=25, mouse_delay=None, mouse_mask=None, **kwargs):
		super().__init__(*args, **kwargs)
		self.frame_delay = 1/frame_rate
		self.proc_delay = int(10//proc_rate)
		self.esc_delay = esc_delay
		self.mouse_delay = self.mouse_delay
		self.mouse_mask = self.mouse_mask

	def init(self):
		super().init()
		if (self.proc_delay > 0): curses.halfdelay(self.proc_delay)
		if (self.esc_delay > 0): curses.set_escdelay(self.esc_delay)
		if (self.mouse_delay is not None): curses.mouseinterval(self.mouse_delay)
		if (self.mouse_mask is not None): curses.mousemask(self.mouse_mask)

	def quit(self):
		self.views.clear()

	def _run_loop(self, stdscr):
		self.stdscr = stdscr
		self.init()

		try:
			while (True):
				if (not self.views): break

				self.proc()

				try: self.key(SCKey(self.stdscr.get_wch()))
				except curses.error:
					if (time.time() < self.lastframe+self.frame_delay): continue
					self.key(SCKey(-1))

				self.draw()
				curses.doupdate()

				self.lastframe = time.time()
		finally:
			self.die()
			self.stdscr = None

	def run(self):
		return curses.wrapper(self._run_loop)

class SCKey(TypeInit):
	# public:
	c: int
	ch: str

	@dispatch
	def __init__(self, c: int):
		self.c, self.ch = c, chr(c) if (c != -1) else ''

	@dispatch
	def __init__(self, ch: lambda ch: isinstance(ch, str) and len(ch) == 1):
		self.c, self.ch = ord(ch), ch

	@dispatch
	def __init__(self, ch: lambda ch: isinstance(ch, str) and len(ch) == 2 and ch[0] == '^'):
		c = (string.ascii_uppercase.index(ch[-1]) + 1)
		self.c, self.ch = c, chr(c)

	@dispatch
	def __init__(self, k: lambda k: isinstance(k, SCKey)):
		self.c, self.ch = k.c, k.ch

	def __repr__(self):
		return f"{self.c} ({repr(self.ch)})"

	def __hash__(self):
		return hash(self.c)

	def __bool__(self):
		return (self.c > 0)

	def __eq__(self, c):
		if (c and isinstance(c, str) and c[0] == '^'): c = (string.ascii_uppercase.index(c[-1]) + 1)
		return (c in (self.c, self.ch))

class SCView(TypeInit):
	# public:
	width: int
	height: int
	erase: bool = True
	transparent: bool
	touched: bool
	died: bool

	def __del__(self):
		try: die = self.die
		except AttributeError: pass
		else: die()

	def init(self):
		""" Initialize self after `curses.initscr()'. """

		self.touch()

	def die(self) -> bool -- ret:
		if (self.died): return True  # exactly in that order
		self.died = True

	def proc(self) -> bool -- ret:
		""" Process before `.draw()', e.g. check some condition to call `.touch()'.
		Note there's no `stdscr' passed here.
		You may use `.touched' meant for the upcoming frame here.
		Return: (ret)
			ret: stop recursive subclass processing.
		"""

	def draw(self, stdscr) -> bool -- ret:
		""" Draw self to `stdscr'.
		Return: (ret)
			ret: stop recursive subclass processing.
		"""

		if (not self.touched): return True
		self.touched = False
		self.height, self.width = stdscr.getmaxyx()
		if (self.erase and not self.transparent): stdscr.erase()

	def touch(self):
		self.touched = True

	def touchAll(self):
		self.touch()

	def key(self, c: SCKey) -> bool -- ret:
		""" Key pressed callback.
		Return: (ret)
			ret: stop recursive subclass processing.
		"""

class SCTestView(SCView):
	char: str

	def __init__(self, char):
		super().__init__()
		self.char = char[0]

	def draw(self, stdscr) -> bool -- ret:
		ret = super().draw(stdscr)
		if (not ret):
			try: stdscr.addch(self.char)
			except curses.error: pass
		return ret

class SCWindowView(SCView):
	win: SCWindow

	def __init__(self, win):
		super().__init__()
		self.win = win

	def init(self):
		super().init()
		self.win.app = self.app
		self.win.stdscr = curses.newpad(1, 1)
		self.win.init()

	def die(self):
		super().die()
		self.win.die()

	def proc(self) -> bool -- ret:
		ret = super().proc()
		if (ret):
			self.win.proc()
			if (self.win.touched): self.touch()
		return ret

	def draw(self, stdscr) -> bool -- ret:
		ret = super().draw(stdscr)
		if (not ret):
			self.win.stdscr.resize(self.height, self.width)
			self.win.loop(0, 0, 0, 0, self.height, self.width)
		return ret

	def touch(self):
		super().touch()
		self.win.touch()

	def touchAll(self):
		super().touchAll()
		self.win.touchAll()

	def key(self, c: SCKey) -> bool -- ret:
		ret = self.key(c)
		if (not ret):
			ret = self.win.key(c)
		return ret

class SCSplitView(SCView, ABCTypeInit):
	erase = False

	# public:
	s: tuple[int]
	p: tuple[SCWindow]
	focus: int

	def __init__(self, *s, focus=0):
		super().__init__()
		self.s, self.focus = s, focus
		self.p = tuple(SCWindow() for _ in range(len(self.s)))

	def init(self):
		super().init()
		for win in self.p:
			win.app = self.app
			win.stdscr = curses.newpad(1, 1)
			win.init()

	def die(self):
		super().die()
		for win in self.p:
			win.die()

	def proc(self) -> bool -- ret:
		ret = super().proc()
		if (not ret):
			for win in self.p:
				win.proc()
				if (win.touched): self.touch()
		return ret

	@abc.abstractmethod
	def draw(self, stdscr) -> bool -- ret:
		return super().draw(stdscr)

	def touch(self):
		super().touch()
		for win in self.p:
			win.touch()

	def touchAll(self):
		super().touchAll()
		for win in self.p:
			win.touchAll()

	def key(self, c: SCKey) -> bool -- ret:
		ret = super().key(c)
		if (not ret):
			ret = self.p[self.focus].key(c)
		return ret

class SCVSplitView(SCSplitView):
	def draw(self, stdscr) -> bool -- ret:
		ret = super().draw(stdscr)
		if (not ret):
			s = round((self.height - sum(self.s)) / self.s.count(0))
			sl = (0, *(p for p in [0] for i in self.s for p in [p + (i or s)]))

			for i in range(len(self.p)):
				self.p[i].stdscr.resize(sl[i+1]-sl[i], self.width)
				self.p[i].loop(0, 0, sl[i], 0, sl[i+1], self.width)
		return ret

class SCHSplitView(SCSplitView):
	def draw(self, stdscr) -> bool -- ret:
		ret = super().draw(stdscr)
		if (not ret):
			s = round((self.width - sum(self.s)) / self.s.count(0))
			sl = (0, *(p for p in [0] for i in self.s for p in [p + (i or s)]))

			for i in range(len(self.p)):
				self.p[i].stdscr.resize(self.height, sl[i+1]-sl[i])
				self.p[i].loop(0, 0, 0, sl[i], self.height, sl[i+1])
		return ret

class SCListView(SCView):
	# public:
	l: list
	t: int; 'view offset'

	def __init__(self, l):
		super().__init__()
		self.l = l

	def draw(self, stdscr) -> bool -- ret:
		ret = super().draw(stdscr)
		if (not ret):
			for i in range(self.t, min(self.t + self.height, len(self.l))):
				ret, items = self.item(i)
				stdscr.move(i-self.t, 0)
				for text, attrs in items:
					try: stdscr.addstr(text, attrs)
					except curses.error: pass  # last character of the screen
		return ret

	def key(self, c: SCKey) -> bool -- ret:
		if (c == curses.KEY_UP):
			self.t -= 1
			self.touch()
		elif (c == curses.KEY_DOWN):
			self.t += 1
			self.touch()
		else: return super().key(c)
		return True

	def item(self, i) -> (bool -- ret, list[tuple[str -- text, int -- attrs]] -- items):
		""" Return list item for `self.l[i]'.
		Return: (ret, items)
			ret: stop recursive subclass processing.
			items: list of (text, attrs) pairs (see `curses.window.addstr()')
		"""

		if (not 0 <= i < len(self.l)): return (True, [])
		return (False, [(str(self.l[i]), int())])

class SCLoadingListView(SCListView):
	class LoadItem(Slots):
		# public:
		has_more: bool
		next_value: ...

		def __init__(self, has_more=True, next_value=None):
			self.has_more, self.next_value = has_more, next_value

	# public:
	to_load: bool; 'needs loading'
	loading: bool; 'loading is in process'

	def __init__(self, l):
		super().__init__(l)

	def init(self):
		super().init()
		if (not self.l): self.to_load = True
		else: self.l.append(self.LoadItem())

	def draw(self, stdscr) -> bool -- ret:
		ret = super().draw(stdscr)
		if (not ret):
			if (self.to_load or self.loading):
				stdscr.addstr(0, 0, "Loading".center(self.width), curses.A_STANDOUT)
				self.touch()

			if (self.to_load):
				self.to_load = False
				self.loading = True
				ret = True
			elif (self.loading):
				self.loading = False
				self.load()
		return ret

	def load(self) -> bool -- ret:
		""" Load new items.
		Last item added should be a `LoadItem'.
		Return: (ret)
			ret: stop recursive subclass processing.
		"""

		self.to_load = self.loading = False

		if (self.l and isinstance(li := self.l[-1], self.LoadItem)):
			if (not li.has_more): li.next_value = None; return True
			else: self.l.pop()

	def reload(self, cleared: bool = False):
		if (not cleared): self.l.clear()
		self.to_load = True
		self.touch()

class SCSelectingListView(SCListView):
	class EmptyItem(Slots):
		def __str__(self):
			return ''

	# public:
	n: int; 'highlighted line'
	s: int; 'selected line'

	def __init__(self, l):
		super().__init__(l)
		self.unselect()

	#def draw(self, stdscr) -> bool -- ret:
	#	self.n = max(0, min(len(self.l)-1, self.n))
	#	return super().draw(stdscr)

	def key(self, c: SCKey) -> bool -- ret:
		if (c == curses.KEY_UP):
			n = self.n
			while (n > 0):
				n -= 1
				if (not self.is_empty(n)):
					self.n = n
					self.touch()
					break
			self.scrollToHighlighted()
		elif (c == curses.KEY_DOWN):
			n = self.n
			while (n < len(self.l)-1):
				n += 1
				if (not self.is_empty(n)):
					self.n = n
					self.touch()
					break
			self.scrollToHighlighted()
		elif (c == curses.KEY_IC):
			#self.n = max(0, self.n-1)
			self.t = max(0, self.t-1)
			self.touch()
		elif (c == curses.KEY_DC):
			#self.n = min(self.n+1, len(self.l)-1)
			self.t = min(self.t+1, max(len(self.l) - self.height+1, 0))
			self.touch()
		elif (c == curses.KEY_PPAGE):
			self.n = max(self.n - self.height, 0)
			while (self.n < len(self.l)-1 and self.is_empty(self.n)):
				self.n += 1
			self.touch()
			self.scrollToHighlighted()
		elif (c == curses.KEY_NPAGE):
			self.n = min(self.n + self.height, len(self.l)-1)
			while (self.n > 0 and self.is_empty(self.n)):
				self.n -= 1
			self.touch()
			self.scrollToHighlighted()
		elif (c == curses.KEY_HOME):
			self.n = 0
			while (self.n < len(self.l)-1 and self.is_empty(self.n)):
				self.n += 1
			self.touch()
			self.scrollToHighlighted()
		elif (c == curses.KEY_END):
			self.n = len(self.l)-1
			while (self.n > 0 and self.is_empty(self.n)):
				self.n -= 1
			self.touch()
			self.scrollToHighlighted()
		elif (c == curses.ascii.NL):
			self.select()
		else: return super().key(c)
		return True

	def is_empty(self, i) -> bool:
		if (not 0 <= i < len(self.l)): return True
		return isinstance(self.l[i], self.EmptyItem)

	def item(self, i):
		ret, items = super().item(i)
		if (not ret):
			for ii, (text, attrs) in enumerate(items):
				attrs |= (curses.A_STANDOUT*(i==self.n) | curses.A_BOLD*(i==self.s))
				items[ii] = (text, attrs)
		return (ret, items)

	def scrollToTop(self):
		self.n = 0
		self.t = 0
		self.touch()

	def scrollToHighlighted(self):
		if (self.t > self.n):
			self.t = max(self.n, 0)
			self.touch()

		if (self.t + self.height <= self.n):
			self.t = min(self.n - self.height+1, len(self.l) - self.height+1)
			self.touch()

	def highlightAndScroll(self, n) -> bool:
		if (self.is_empty(n)): return False
		self.n = n
		self.touch()
		self.scrollToHighlighted()
		return True

	def setSelection(self, n) -> bool:
		if (self.is_empty(n)): return False
		self.s = n
		self.touch()
		return True

	def select(self) -> bool -- ret:
		""" Select currently highlighted item.
		Return: (ret)
			ret: stop recursive subclass processing.
		"""

		if (not self.setSelection(self.n)): return True

	def unselect(self):
		self.s = -1
		self.touch()

class SCLoadingSelectingListView(SCLoadingListView, SCSelectingListView):
	def key(self, c: SCKey) -> bool -- ret:
		if (c == curses.KEY_DOWN):
			n = self.n
			while (n < len(self.l)-1-bool(self.l and isinstance(li := self.l[-1], self.LoadItem) and not li.has_more)):
				n += 1
				if (not self.is_empty(n)):
					self.n = n
					self.touch()
					break
			self.scrollToHighlighted()
		elif (c == curses.KEY_DC):
			#self.n = min(self.n + 1, len(self.l) - 1 - bool(not (isinstance(li := self.l[-1], self.LoadItem) and li.has_more)))
			self.t = min(self.t + 1, max(len(self.l) - self.height - bool(self.l and isinstance(li := self.l[-1], self.LoadItem) and not li.has_more), 0))
			self.touch()
		elif (c == curses.KEY_NPAGE):
			self.n = min(self.n + self.height, len(self.l) - 1 - bool(self.l and isinstance(li := self.l[-1], self.LoadItem) and not li.has_more))
			while (self.n > 0 and self.is_empty(self.n)):
				self.n -= 1
			self.touch()
			self.scrollToHighlighted()
		elif (c == curses.KEY_END):
			self.n = len(self.l)-1-bool(self.l and isinstance(li := self.l[-1], self.LoadItem) and not li.has_more)
			while (self.n > 0 and self.is_empty(self.n)):
				self.n -= 1
			self.touch()
			self.scrollToHighlighted()
		else: return super().key(c)
		return True

	def is_empty(self, i) -> bool:
		if (super().is_empty(i)): return True
		return (isinstance(li := self.l[i], self.LoadItem) and not li.has_more)

	def item(self, i):
		ret, items = super().item(i)
		if (not ret):
			if (isinstance(li := self.l[i], self.LoadItem)):
				attrs = items[0][1]
				if (not li.has_more):
					text = "End."
					attrs |= curses.A_DIM
				elif (self.loading): text = "Loading..."
				else: text = "Load more..."
				items = [(text, attrs)]
				ret = True
		return (ret, items)

	def select(self) -> bool -- ret:
		ret = super().select()
		if (not ret):
			if (isinstance(li := self.l[self.n], self.LoadItem)):
				if (not li.has_more):
					self.n -= 1
					self.touch()
				else: self.to_load = True
				ret = True
		return ret

class SCTextBox(SCView):
	# public:
	tabsize: 8
	lines: lambda: Sdict(str)
	line: int
	col: int
	yoff: int

	# properties:
	text: str
	nlines: int
	cline: str

	def init(self):
		super().init()
		self.app.stdscr.leaveok(False)

	def _drawLine(self, stdscr, ln: int, l: str, *, x: int = 0, y: int = 0):
		ii = None
		for ii, c in enumerate(l):
			try: stdscr.addch(y, x, c if (c != '\t') else ' ', curses.A_STANDOUT*(ln == self.line and ii == self.col))
			except curses.error: pass  # last character of the screen
			x += (self.tabsize if (c == '\t') else 1)
			if (x >= self.width): y += 1; x = 0
			if (y >= self.height): break

		if (ln == self.line and (ii is None or ii < self.col) and self.col < self.width):
			try: stdscr.addch(y, x, ' ', curses.A_STANDOUT)
			except curses.error: pass

		return (x, y)

	def draw(self, stdscr) -> bool -- ret:
		ret = super().draw(stdscr)
		if (not ret):
			x = y = pln = int()
			y -= self.yoff

			ln = int()
			for ln, l in sorted(self.lines.items()):
				y += (ln - pln)
				if (y >= self.height): break

				x, y = self._drawLine(stdscr, ln, l, y=y)
				if (y >= self.height): break

				pln = ln

			if (ln < self.line and self.line < self.height and x <= self.col and self.col < self.width):
				stdscr.addch(y, min(self.col, len(self.lines[self.line])), ' ', curses.A_STANDOUT | curses.A_DIM)

			self.ycnt = y
		return ret

	def key(self, c: SCKey) -> bool -- ret:
		ch = SCKey(c) # XXX?
		self.app.debugOut(ch)
		#y, x = self.stdscr.getyx()

		#elif (ch == curses.ascii.SOH): # ^A
		#	self.stdscr.move(y, 0)
		#elif (ch == curses.ascii.EOT): # ^D
		#	self.stdscr.delch()
		#elif (ch == curses.ascii.ENQ): # ^E
		#	if (self.stripspaces): self.stdscr.move(y, self._end_of_line(y))
		#	else: self.stdscr.move(y, self.width-1)
		#elif (ch in (curses.ascii.ACK, curses.KEY_RIGHT)): # ^F
		#	if (x < self.width-1): self.stdscr.move(y, x+1)
		#	elif (y == self.height-1): pass
		#	else: self.stdscr.move(y+1, 0)
		#elif (ch == curses.ascii.BEL): # ^G
		#	pass #ret = True
		#elif (ch == curses.ascii.NL): # ^J
		#	if (self.height-1 == 0): pass #ret = True
		#	elif (y < self.height-1): self.stdscr.move(y+1, 0)
		#elif (ch == curses.ascii.VT): # ^K
		#	if (x == 0 and self._end_of_line(y) == 0): self.stdscr.deleteln()
		#	else:
		#		self.stdscr.move(y, x)
		#		self.stdscr.clrtoeol()
		#elif (ch == curses.ascii.FF): # ^L
		#	self.touch()
		#elif (ch in (curses.ascii.SO, curses.KEY_DOWN)): # ^N
		#	if (y < self.height-1):
		#		self.stdscr.move(y+1, x)
		#		if (x > self._end_of_line(y+1)): self.stdscr.move(y+1, self._end_of_line(y+1))
		#elif (ch == curses.ascii.SI): # ^O
		#	self.stdscr.insertln()
		#elif (ch in (curses.ascii.DLE, curses.KEY_UP)): # ^P
		#	if (y > 0):
		#		self.stdscr.move(y-1, x)
		#		if (x > self._end_of_line(y-1)): self.stdscr.move(y-1, self._end_of_line(y-1))
		if (ch == curses.KEY_LEFT):
			self.col = min(self.col, len(self.cline))-1
			if (self.col < 0):
				if (self.line > 0):
					self.line -= 1
					if (self.line < self.yoff): self.yoff -= 1
					self.col = len(self.cline)
				else: self.col = 0
			self.touch()
		elif (ch == curses.KEY_RIGHT):
			if (self.line <= self.nlines):
				self.col += 1
				if (self.col > len(self.cline) and self.line < self.nlines):
					self.line += 1
					if (self.line >= self.yoff + self.height): self.yoff += 1
					self.col = 0
				self.touch()
		elif (ch == curses.KEY_UP):
			if (self.line > 0):
				self.line -= 1
				if (self.line < self.yoff): self.yoff -= 1
				self.touch()
		elif (ch == curses.KEY_DOWN):
			if (self.line < self.nlines):
				self.line += 1
				if (self.line >= self.yoff + self.height): self.yoff += 1
				self.touch()
		elif (ch == curses.KEY_HOME):
			self.col = 0
			self.touch()
		elif (ch == curses.KEY_END):
			self.col = len(self.cline)
			self.touch()
		elif (ch == curses.KEY_PPAGE):
			if (self.line - self.height > 0):
				self.line -= self.height
				self.yoff -= self.height
			elif (self.line == 0): self.col = 0
			else: self.line = self.yoff = 0
			self.touch()
		elif (ch == curses.KEY_NPAGE):
			if (self.line + self.height < self.nlines):
				self.line += self.height
				self.yoff += self.height
			elif (self.line == self.nlines): self.col = len(self.cline)
			else: self.line = self.nlines#+1
			self.touch()
		elif (ch == 536):  # ^Home
			self.line = self.col = self.yoff = 0
			self.touch()
		elif (ch == 531):  # ^End
			self.line = self.nlines
			self.yoff = max(self.line - self.height + 1, 0)
			self.col = len(self.cline)
			self.touch()
		elif (ch == 565):  # M-Up
			if (self.yoff > 0):
				self.yoff -= 1
				self.touch()
		elif (ch == 524):  # M-Down
			if (self.yoff < self.nlines):
				self.yoff += 1
				self.touch()
		elif (ch in (curses.KEY_BACKSPACE, curses.ascii.BS, curses.ascii.DEL)):
			if (self.cline):
				self.col = min(self.col-1, len(self.cline))
				if (self.col >= 0): self.cline = (self.cline[:self.col] + self.cline[self.col+1:])
				else:
					line = self.cline; del self.cline
					self.line -= 1
					self.col = len(self.cline)
					self.cline += line
				self.touch()
			else:
				del self.cline
				self.line = max(0, self.line-1)
				self.col = len(self.cline)
				self.touch()
		elif (ch in (curses.KEY_DC, curses.ascii.DEL)):
			if (self.cline):
				self.col = min(self.col, len(self.cline))
				if (self.col < len(self.cline)): self.cline = (self.cline[:self.col] + self.cline[self.col+1:])
				#else:
				self.touch()
			else:
				del self.cline
				self.line = max(0, self.line-1)
				self.col = len(self.cline)
				self.touch()
		elif (ch == curses.ascii.NL):
			for ii, i in sorted(self.lines.items(), reverse=True):
				if (ii <= self.line): break
				self.lines[ii+1] = i
			cline = self.cline
			self.cline = cline[:self.col]
			self.line += 1
			self.cline = cline[self.col:]
			self.col = 0
			self.touch()
		elif (ch == '^K'):
			del self.cline
			if (self.line <= self.yoff): self.yoff -= 1
			if (not self.cline):
				self.line = self.nlines
				self.col = len(self.cline)
			self.touch()
		elif (ch.ch.isprintable() or ch == '\t'):
			self.cline = (self.cline[:self.col] + ch.ch + self.cline[self.col:])
			self.col += 1 #(self.col//8*8 if (ch == '\t') else 1)
			self.touch()
		else: return super().key(c)
		return True

	@property
	def text(self) -> str:
		return '\n'.join(self.lines.get(i, '') for i in range(max(self.lines, default=0)+1))

	@text.setter
	def text(self, s: str | list):
		self.lines.clear()
		if (isinstance(s, str)): s = s.split('\n')
		ii = None
		for ii, i in enumerate(s):
			self.lines[ii] = i.rstrip('\n')
		if (ii is not None and i.endswith('\n')): self.lines[ii+1] = ''

	@property
	def nlines(self) -> int:
		#return max((k for k, v in self.lines.items() if v), default=0)
		return max(self.lines, default=0)

	@property
	def cline(self) -> str:
		return self.lines.get(self.line, '')

	@cline.setter
	def cline(self, x: str):
		self.lines[self.line] = x

	@cline.deleter
	def cline(self):
		ml = None
		for ii, i in sorted(self.lines.items(), reverse=True):
			if (ii <= self.line): break
			if (ml is None): ml = ii
			self.lines[ii-1] = i
		self.lines.pop(ml if (ml is not None) else self.line, '')

class SCLinedTextBox(SCTextBox):
	def _drawLine(self, stdscr, ln: int, l: str, *, x: int = 0, y: int = 0):
		lnw = len(S(max(self.lines, default=0)))
		try: stdscr.addstr(y, x, str(ln+1).rjust(lnw), curses.A_DIM)
		except curses.error: pass
		x += lnw+1
		return super()._drawLine(stdscr, ln, l, x=x, y=y)

if (__name__ == '__main__'): logstarted(); exit()
else: logimported()

# by Sdore, 2019-22
#   www.sdore.me
