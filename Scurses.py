#!/usr/bin/python3
# Scurses

import curses, curses.textpad
from abc import *
from utils import *; logstart('Scurses')

class SCKey:
	def __init__(self, c):
		if (isinstance(c, str)): self.c, self.ch = ord(c), c
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

	def debugOut(self, *s, sep=' '):
		self.debugstr = S(sep.join(map(str, s))).wrap(self.stdscr.getmaxyx()[1]//2).split('\n')

	def draw(self):
		h, w = self.stdscr.getmaxyx()
		if (self.views): self.views[-1].draw(self.stdscr)
		for ii, i in enumerate(self.debugstr):
			if (ii >= h): break
			self.stdscr.addstr(ii, (w-len(i))//2-1, i, curses.A_STANDOUT)

	def key(self, c):
		if (not c): return
		self.debugOut()
		for view in self.views[::-1]:
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

	def loop(self, *rargs):
		self.draw()
		self.stdscr.noutrefresh(*rargs)

class SCApp(SCWindow):
	def __init__(self, frame_rate=60):
		super().__init__()
		self.frame_delay = 1/frame_rate
		self.stopped = bool()

	def quit(self):
		self.views = None

	def loop(self):
		self.draw()
		curses.doupdate()
		self.key(SCKey(self.stdscr.getch()))

	def _run_loop(self, stdscr):
		self.stdscr = stdscr
		self.init()
		while (True):
			try:
				start = time.time()
				self.loop()
				if (not self.views): break
				delay_left = self.frame_delay-(time.time()-start)
				if (delay_left > 0): time.sleep(delay_left) # optimization; sleep(0) takes more time.
			except KeyboardInterrupt: break
		self.stdscr = None

	def run(self):
		return curses.wrapper(self._run_loop)

class SCView:
	def init(self):
		" Initialize self after curses.initscr() "

	def draw(self, stdscr):
		" Draw self to `stdscr' "
		self.h, self.w = stdscr.getmaxyx()
		stdscr.erase()

	def key(self, c):
		" Key pressed callback "

class SCSplitView(SCView, ABC):
	def __init__(self, s, focus=0):
		self.s, self.focus = s, focus
		self.p = (SCWindow(), SCWindow())

	def init(self):
		for i in self.p:
			i.app = self.app
			i.stdscr = curses.newpad(1, 1)
			i.init()

	@abstractmethod
	def draw(self, stdscr):
		pass

	def key(self, c):
		return self.p[self.focus].key(c)

class SCVSplitView(SCSplitView):
	def draw(self, stdscr):
		self.h, self.w = stdscr.getmaxyx()
		s = self.h+self.s if (self.s < 0) else self.s
		self.p[0].stdscr.resize(s, self.w)
		self.p[1].stdscr.resize(self.h-s, self.w)
		self.p[0].loop(0, 0, 0, 0, s, self.w)
		self.p[1].loop(0, 0, s, 0, self.h, self.w)

class SCHSplitView(SCSplitView):
	def draw(self, stdscr):
		self.h, self.w = stdscr.getmaxyx()
		s = self.w+self.s if (self.s < 0) else self.s
		self.p[0].stdscr.resize(self.h, s)
		self.p[1].stdscr.resize(self.h, self.w-s)
		self.p[0].loop(0, 0, 0, 0, self.h, s)
		self.p[1].loop(0, 0, 0, s, self.h, self.w)

class SCListView(SCView):
	def __init__(self, l):
		self.l = l # List
		self.t = int() # View offset
		self.h = self.w = int()

	def draw(self, stdscr):
		super().draw(stdscr)
		for i in range(self.t, min(self.t+self.h, len(self.l))):
			stdscr.addstr(i-self.t, 0, *self.item(i))

	def key(self, c):
		if (c == curses.KEY_UP): self.t -= 1
		elif (c == curses.KEY_DOWN): self.t += 1
		else: return False
		return True

	def item(self, i):
		return (str(self.l[i]), 0)

class SCSelectingListView(SCListView):
	def __init__(self, l):
		super().__init__(l)
		self.n = int() # Current line
		self.s = -1 # Selected line

	def draw(self, stdscr):
		self.n = max(0, min(len(self.l)-1, self.n))
		super().draw(stdscr)

	def key(self, c):
		if (c == curses.KEY_UP):
			self.n = max(0, self.n-1)
			self.scrollToSelected()
		elif (c == curses.KEY_DOWN):
			self.n = min(self.n+1, len(self.l)-1)
			self.scrollToSelected()
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
		elif (c == '\n'):
			self.select()
		else: return super().key(c)
		return True

	def item(self, i):
		text, attrs = super().item(i)
		attrs |= curses.A_STANDOUT*(i==self.n) | curses.A_BOLD*(i==self.s)
		return (text, attrs)

	def scrollToTop(self):
		self.n = 0
		self.t = 0

	def scrollToSelected(self):
		if (self.t > self.n): self.t = max(self.n, 0)
		if (self.t+self.h <= self.n): self.t = min(self.n-self.h+1, len(self.l)-self.h+1)

	def selectAndScroll(self, n):
		self.n = n
		self.s = self.n
		self.scrollToSelected()

	def select(self):
		self.s = self.n

if (__name__ == '__main__'): logstarted(); exit()
else: logimported()

# by Sdore, 2019
