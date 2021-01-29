#!/usr/bin/python3
# Scurses

import curses, curses.ascii, curses.textpad
from utils import *; logstart('Scurses')

MOUSE_WHEEL = curses.BUTTON4_PRESSED | 2097152#curses.REPORT_MOUSE_POSITION |

class SCKey:
	__slots__ = ('c', 'ch')

	def __init__(self, c):
		if (isinstance(c, SCKey)): self.c, self.ch = c.c, c.ch; return
		if (isinstance(c, str)):
			if (len(c) == 1):
				self.ch = c
				self.c = ord(self.ch)
			elif (c[0] == '^' and len(c) == 2):
				self.c = string.ascii_uppercase.index(c[-1])+1
				self.ch = chr(self.c)
			else: raise ValueError(c)
		elif (isinstance(c, int)): self.c, self.ch = c, chr(c) if (c != -1) else ''
		else: raise TypeError()

	def __repr__(self):
		return f"{self.c} ({repr(self.ch)})"

	def __hash__(self):
		return hash(self.c)

	def __bool__(self):
		return self.c > 0

	def __eq__(self, c):
		return c in (self.c, self.ch)

class SCWindow:
	def __init__(self, stdscr=None, app=None):
		self.stdscr = stdscr
		self.app = app
		self.key_handlers = dict()
		self.views = list()
		self.inited = bool()
		self.waitrelease = None
		self.waitrelease_pressed = bool()
		self.waitrelease_lastpressed = int()
		self.debugstr = str()

	def init(self):
		self.stdscr.nodelay(True)
		for view in self.views:
			view.init()
		self.inited = True

	def addView(self, view):
		view.app = self.app or self
		self.views.append(view)
		if (self.inited): view.init()

	def popView(self):
		del self.views[-1]
		if (self.views): self.views[-1].touch()

	def debugOut(self, *s, sep=' '):
		self.debugstr = S(sep.join(map(str, s))).wrap(self.stdscr.getmaxyx()[1]//2).split('\n')

	def draw(self):
		h, w = self.stdscr.getmaxyx()
		for view in self.views:
			view.draw(self.stdscr)
		if (not self.debugstr): return
		for ii, i in enumerate(self.debugstr):
			if (ii >= h): break
			self.stdscr.addstr(ii, (w-len(i))//2-1, i, curses.A_STANDOUT)

	def key(self, c):
		if (not c): return
		if (self.waitrelease):
			if (c != self.waitrelease or time.time()-self.waitrelease_lastpressed > 0.05): self.waitrelease = None
			else: self.waitrelease_lastpressed = time.time(); return
		self.debugOut()
		for view in self.views[::-1]:
			if (c == curses.KEY_RESIZE):
				view.touch()
			r = view.key(c)
			if (r): return r
		else:
			if (c in self.key_handlers): return self.key_handlers[c](self, c)
			elif (... in self.key_handlers): return self.key_handlers[...](self, c)

	def onkey(self, c):
		if (callable(c)): return self.onkey(c.__name__)(c)
		return lambda f: self.key_handlers.__setitem__(SCKey(c), f) or f

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
	def top(self):
		return self.views[-1]

class SCApp(SCWindow):
	def __init__(self, *, frame_rate=60, proc_rate=60):
		super().__init__()
		self.frame_delay = 1/frame_rate
		self.proc_delay = int(10//proc_rate)
		self.lastframe = 0
		self.stopped = bool()

	def init(self):
		super().init()
		if (self.proc_delay > 0): curses.halfdelay(self.proc_delay)

	def quit(self):
		self.views = None

	def _run_loop(self, stdscr):
		self.stdscr = stdscr
		self.init()
		while (True):
			try:
				if (not self.views): break
				self.proc()
				try: self.key(SCKey(self.stdscr.get_wch()))
				except curses.error:
					if (time.time() < self.lastframe+self.frame_delay): continue
					self.key(SCKey(-1))
				self.draw()
				curses.doupdate()
				self.lastframe = time.time()
			except KeyboardInterrupt: break
		self.stdscr = None

	@staticmethod
	def proc(): pass

	def run(self):
		return curses.wrapper(self._run_loop)

class SCView:
	def __init__(self):
		self.touched = True

	def init(self):
		""" Initialize self after curses.initscr() """

	def draw(self, stdscr):
		""" Draw self to `stdscr'
		Return: (ret)
			ret: force stop recursive subclass processing.
		"""

		if (not self.touched): return True
		self.touched = False
		self.h, self.w = stdscr.getmaxyx()
		stdscr.erase()

	def touch(self):
		self.touched = True

	def key(self, c):
		""" Key pressed callback """

class SCTestView(SCView):
	def __init__(self, char):
		super().__init__()
		self.char = char[0]

	def draw(self, stdscr):
		if (super().draw(stdscr)): return True
		try:
			while (True): stdscr.addch(self.char)
		except curses.error: pass

### TODO?
#class SCWindowView(SCView):
#	def __init__(self):
#		super().__init__()
#		self.w = SCWindow()
#
#	def init(self):
#		self.w.app = self.app
#		self.w.stdscr = curses.newpad(1, 1)
#		self.w.init()
#
#	def draw(self, stdscr):
#		if (not self.touched): return True
#		self.h, self.w = stdscr.getmaxyx()
#		self.w.stdscr.resize(self.h, self.w)
#		self.w.loop(0, 0, 0, 0, self.h, self.w)
#
#	def key(self, c):
#		return self.w.key(c)
###

class SCSplitView(SCView, abc.ABC):
	def __init__(self, *s, focus=0):
		super().__init__()
		self.s, self.focus = s, focus
		self.p = tuple(SCWindow() for _ in range(len(self.s)))

	def init(self):
		for w in self.p:
			w.app = self.app
			w.stdscr = curses.newpad(1, 1)
			w.init()

	@abc.abstractmethod
	def draw(self, stdscr):
		pass

	def touch(self):
		super().touch()
		for w in self.p:
			w.top.touch()

	def key(self, c):
		return self.p[self.focus].key(c)

class SCVSplitView(SCSplitView):
	def draw(self, stdscr):
		if (any(w.top.touched for w in self.p if w.views)): self.touched = True
		if (not self.touched): return True
		self.h, self.w = stdscr.getmaxyx()

		s = round((self.h-sum(self.s))/self.s.count(0))
		sl = (0, *(p for p in [0] for i in self.s for p in [p + (i or s)]))

		for i in range(len(self.p)):
			self.p[i].stdscr.resize(sl[i+1]-sl[i], self.w)
			self.p[i].loop(0, 0, sl[i], 0, sl[i+1], self.w)

class SCHSplitView(SCSplitView):
	def draw(self, stdscr):
		if (any(w.top.touched for w in self.p if w.views)): self.touched = True
		if (not self.touched): return True
		self.h, self.w = stdscr.getmaxyx()

		s = round((self.w-sum(self.s))/self.s.count(0))
		sl = (0, *(p for p in [0] for i in self.s for p in [p + (i or s)]))

		for i in range(len(self.p)):
			self.p[i].stdscr.resize(self.h, sl[i+1]-sl[i])
			self.p[i].loop(0, 0, 0, sl[i], self.h, sl[i+1])

class SCListView(SCView):
	def __init__(self, l):
		super().__init__()
		self.l = l # List
		self.t = int() # View offset
		self.h = self.w = int()

	def draw(self, stdscr):
		if (super().draw(stdscr)): return True
		for i in range(self.t, min(self.t+self.h, len(self.l))):
			ret, items = self.item(i)
			stdscr.move(i-self.t, 0)
			for text, attrs in items:
				stdscr.addstr(text, attrs)

	def key(self, c):
		if (c == curses.KEY_UP): self.t -= 1; self.touch()
		elif (c == curses.KEY_DOWN): self.t += 1; self.touch()
		else: return False
		return True

	def item(self, i):
		""" Return list item for `self.l[i]'
		Return: (ret, items)
			ret: force stop recursive subclass processing.
			items: list of (text, attrs) pairs (see `curses.window.addstr()')
		"""

		return (False, [(str(self.l[i]), 0)])

class SCLoadingListView(SCListView):
	class LoadItem:
		def __init__(self, has_more=True, next_value=None):
			self.has_more, self.next_value = has_more, next_value

	def __init__(self, l):
		super().__init__(l)
		self.l.append(self.LoadItem())
		self.toLoad = bool()
		self.loading = bool()

	def draw(self, stdscr):
		if (super().draw(stdscr)): return True
		if (self.loading):
			#stdscr.addstr(0, 0, 'Loading'.center(self.w), curses.A_STANDOUT)
			self.loading = False
			self.touch()
			return
		if (not self.l and not self.toLoad):
			self.toLoad = True
			self.touch()
			return
		if (self.toLoad):
			self.load()
			self.touch()
			self.toLoad = False

	def load(self):
		""" Load new items
		Last item added should be a LoadItem.
		Return: (ret)
			ret: force stop recursive subclass processing.
		"""

		if (isinstance(self.l[-1], self.LoadItem)):
			if (not self.l[-1].has_more): self.l[-1].next_value = None; return True
		return False

class SCSelectingListView(SCListView):
	def __init__(self, l):
		super().__init__(l)
		self.n = int() # Current line
		self.s = -1 # Selected line

	def draw(self, stdscr):
		self.n = max(0, min(len(self.l)-1, self.n))
		if (super().draw(stdscr)): return True

	def key(self, c):
		if (c == curses.KEY_UP):
			self.n = max(0, self.n-1)
			self.scrollToSelected()
		elif (c == curses.KEY_DOWN):
			self.n = min(self.n+1, len(self.l)-1)
			self.scrollToSelected()
		elif (c == curses.KEY_IC):
			#self.n = max(0, self.n-1)
			self.t = max(0, self.t-1)
			self.touch()
		elif (c == curses.KEY_DC):
			#self.n = min(self.n+1, len(self.l)-1)
			self.t = min(self.t+1, max(len(self.l)-self.h+1, 0))
			self.touch()
		elif (c == curses.KEY_PPAGE):
			self.n = max(self.n-self.h, 0)
			self.scrollToSelected()
		elif (c == curses.KEY_NPAGE):
			self.n = min(self.n+self.h, len(self.l)-1)
			self.scrollToSelected()
		elif (c == curses.KEY_HOME):
			self.n = 0
			self.scrollToSelected()
		elif (c == curses.KEY_END):
			self.n = len(self.l)-1
			self.scrollToSelected()
		elif (c == curses.ascii.NL):
			self.select()
			self.touch()
		else: return super().key(c)
		return True

	def item(self, i):
		ret, items = super().item(i)
		if (not ret):
			for ii, (text, attrs) in enumerate(items):
				attrs |= curses.A_STANDOUT*(i==self.n) | curses.A_BOLD*(i==self.s)
				items[ii] = (text, attrs)
		return (ret, items)

	def scrollToTop(self):
		self.n = 0
		self.t = 0
		self.touch()

	def scrollToSelected(self):
		if (self.t > self.n): self.t = max(self.n, 0)
		if (self.t+self.h <= self.n): self.t = min(self.n-self.h+1, len(self.l)-self.h+1)
		self.touch()

	def selectAndScroll(self, n):
		self.n = n
		self.s = self.n
		self.scrollToSelected()

	def select(self):
		""" Select currently highlighted item
		Return: (ret)
			ret: force stop recursive subclass processing.
		"""

		self.s = self.n
		return False

class SCLoadingSelectingListView(SCLoadingListView, SCSelectingListView):
	def key(self, c):
		if (c == curses.KEY_DOWN):
			self.n = min(self.n+1, len(self.l)-1-(not self.l[-1].has_more))
			self.scrollToSelected()
		elif (c == curses.KEY_DC):
			#self.n = min(self.n+1, len(self.l)-1-(not self.l[-1].has_more))
			self.t = min(self.t+1, max(len(self.l)-self.h-(not self.l[-1].has_more), 0))
			self.touch()
		elif (c == curses.KEY_NPAGE):
			self.n = min(self.n+self.h, len(self.l)-1-(not self.l[-1].has_more))
			self.scrollToSelected()
		elif (c == curses.KEY_END):
			self.n = len(self.l)-1-(not self.l[-1].has_more)
			self.scrollToSelected()
		else: return super().key(c)
		return True

	def item(self, i):
		ret, items = super().item(i)
		if (not ret):
			if (isinstance(self.l[i], self.LoadItem)):
				if (not self.l[i].has_more): text = 'End.'
				else: text = 'Loading...' if (self.loading) else 'Load more...'
				items = [(text, items[0][1])]
				ret = True
		return (ret, items)

	def select(self):
		if (isinstance(self.l[self.n], self.LoadItem)):
			if (not self.l[self.n].has_more): self.n -= 1
			else: self.loading = True; self.toLoad = True
			return True


class SCTextBox(SCView):
	def __init__(self):
		super().__init__()
		self.line = self.col = 0
		self.lines = Sdict(str)

	def init(self):
		self.app.stdscr.leaveok(False)

	def draw(self, stdscr):
		if (super().draw(stdscr)): return True

		x = y = pln = 0
		for ln, l in sorted(self.lines.items()):
			y += ln-pln
			if (y >= self.h): break

			x = 0
			for c in l:
				assert (c != '\t')
				stdscr.addch(y, x, c, curses.A_STANDOUT*(y == self.line and x == self.col))
				x += 1
				if (x >= self.w): y += 1; x = 0
				if (y >= self.h): break
			if (y >= self.h): break

			if (y == self.line and x <= self.col and self.col < self.w):
				stdscr.addch(self.line, x, ' ', curses.A_STANDOUT)

			pln = ln

		if (y <= self.line and self.line < self.h and x <= self.col and self.col < self.w):
			stdscr.addch(self.line, self.col, ' ', curses.A_STANDOUT)

	def key(self, c):
		ch = SCKey(c)
		#y, x = self.stdscr.getyx()

		#elif (ch == curses.ascii.SOH): # ^A
		#	self.stdscr.move(y, 0)
		#elif (ch == curses.ascii.EOT): # ^D
		#	self.stdscr.delch()
		#elif (ch == curses.ascii.ENQ): # ^E
		#	if (self.stripspaces): self.stdscr.move(y, self._end_of_line(y))
		#	else: self.stdscr.move(y, self.w-1)
		#elif (ch in (curses.ascii.ACK, curses.KEY_RIGHT)): # ^F
		#	if (x < self.w-1): self.stdscr.move(y, x+1)
		#	elif (y == self.h-1): pass
		#	else: self.stdscr.move(y+1, 0)
		#elif (ch == curses.ascii.BEL): # ^G
		#	pass#return False
		#elif (ch == curses.ascii.NL): # ^J
		#	if (self.h-1 == 0): pass#return False
		#	elif (y < self.h-1): self.stdscr.move(y+1, 0)
		#elif (ch == curses.ascii.VT): # ^K
		#	if (x == 0 and self._end_of_line(y) == 0): self.stdscr.deleteln()
		#	else:
		#		self.stdscr.move(y, x)
		#		self.stdscr.clrtoeol()
		#elif (ch == curses.ascii.FF): # ^L
		#	self.touch()
		#elif (ch in (curses.ascii.SO, curses.KEY_DOWN)): # ^N
		#	if (y < self.h-1):
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
				if (self.line > 0): self.col = self.w-1; self.line -= 1
				else: self.col = 0
		elif (ch == curses.KEY_RIGHT):
			self.col += 1
			if (self.col > len(self.cline)): self.line += 1; self.col = 0
		elif (ch == curses.KEY_UP):
			self.line = max(0, self.line-1)
			#self.col = min(self.col, len(self.cline))
		elif (ch == curses.KEY_DOWN):
			self.line += 1
		elif (ch in (curses.ascii.BS, curses.ascii.DEL, curses.KEY_BACKSPACE)):
			if (self.cline):
				self.col = min(self.col, len(self.cline))
				self.cline = self.cline[:self.col-1]+self.cline[self.col:]
				self.col -= 1
				if (self.col < 0): self.col = self.w-1; self.line -= 1
			else:
				del self.cline
				self.line = max(0, self.line-1)
				self.col = 0
		elif (ch == curses.ascii.NL):
			self.line += 1
			self.col = 0
		elif (ch == curses.KEY_STAB):
			self.cline += '\t'
			self.col = self.col//8*8
		elif (ch.ch.isprintable()):
			self.cline += ch.ch
			self.col += 1
		else: return False
		self.touch()
		return True

	@property
	def text(self):
		return '\n'.join(self.lines.get(i, '') for i in range(max(self.lines, default=0)+1))

	@property
	def cline(self):
		return self.lines[self.line]

	@cline.setter
	def cline(self, x):
		self.lines[self.line] = x

	@cline.deleter
	def cline(self):
		del self.lines[self.line]

if (__name__ == '__main__'): logstarted(); exit()
else: logimported()

# by Sdore, 2020
