import sys
import ctypes
import sdl2.ext
import multiprocessing.dummy as mpdummy
import threading
import Queue
import bzpost
import pyfits
import StringIO
import urllib2
import numpy as np

from httplib import BadStatusLine

from sdl2 import *


def bounding_range(*m):
    z = zip(*m)
    return (min(*z[0]), max(*z[1]))


class SnapshotCollection():
    def __init__(self, source, sink):
        self.source = source
        self.sink = sink
        self.thread = threading.Thread(target=self.async)
        self.thread.daemon = True
        self.covered_range = None
        self.cover_reqs = Queue.Queue()

        self.thread.start()

    def cover(self, a, b):
        self.cover_reqs.put((int(a), int(b)))

    def _cover(self, a, b):
        if not a < b:
            return

        a, b = bzpost.normalize_time(a), bzpost.normalize_time(b)

        try:
            for ss in self.source.get_snapshots(a, b):
                if b > ss.time >= a:
                    self.sink(ss)
        except BadStatusLine, e:
            print "oh no, a BadStatusLine!", e # TODO
            self.source.close()
            self.source.connect()

    def async(self):
        while True:
            req = self.cover_reqs.get()

            while not self.cover_reqs.empty():
                req = self.cover_reqs.get_nowait()

            if self.covered_range is None:
                self._cover(req[0], req[1])
                self.covered_range = req
            else:
                new_range = bounding_range(self.covered_range, req)
                self._cover(new_range[0], self.covered_range[0])
                self._cover(self.covered_range[1], new_range[1])
                self.covered_range = new_range


TIME_PER_PIX = 60.0 / 352
BLACK = sdl2.ext.Color(0, 0, 0, 255)


class Window(object):
    def __init__(self, connector):
        self.sdl_window = SDL_CreateWindow(
            connector.base_url,
            SDL_WINDOWPOS_CENTERED,
            SDL_WINDOWPOS_CENTERED,
            500, 600,
            SDL_WINDOW_SHOWN
        )
        self.sdl_surface = SDL_GetWindowSurface(self.sdl_window)
        self.window_id = SDL_GetWindowID(self.sdl_window)
        self.connector = connector
    
    def handle_event(self, event):
        pass

    def render(self, snapshot_surface):
        sdl2.ext.fill(self.sdl_surface.contents, BLACK)
        y = (snapshot['time'] - bzpost.normalize_time(int(time))).total_seconds() / TIME_PER_PIX
        SDL_BlitSurface(snapshot_surface, None, self.sdl_surface, SDL_Rect(10, int(y), 0, 0))
        SDL_UpdateWindowSurface(self.sdl_window)


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Invalid number of arguments.\n")
        sys.stderr.write("Usage: %s BASE_URL, NEXT_BASE_URL \n" % (sys.argv[0], ))
        sys.stderr.write("Example: %s http://space.astro.cz/bolidozor/OBSUPICE/OBSUPICE-R3/\n" % (sys.argv[0], ))
        sys.exit(1)

    SDL_Init(SDL_INIT_VIDEO)

    windows = []

    for i in range(0, len(sys.argv) - 1): 
        try:
            connector = bzpost.HTTPConnector(sys.argv[i+1])
            connector.connect()
        except:
            print "Bolidozor browser cannot contact Bolidozor's data center. Please check the internet connection", e
            sys.exit(main())
        #window = SDL_CreateWindow(connector.base_url,
        #                          SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        #                          500, 600, SDL_WINDOW_SHOWN)
        #window_id = SDL_GetWindowID(window) 
        #windows[window_id] = {'window': window,'window_surface':SDL_GetWindowSurface(window), 'connector': connector}
        windows.append(Window(connector))
        
    main_thread_queue = Queue.Queue()

    def run_on_main_thread(func):
        main_thread_queue.put(func)

        event = SDL_Event()
        event.type = SDL_USEREVENT
        SDL_PushEvent(event)

    thpool = mpdummy.Pool(processes=3)


    drawable_snapshots = []

    def put_up_snapshot(snapshot, window):
        print "downloading %s..." % snapshot.url

        fits = pyfits.open(StringIO.StringIO(urllib2.urlopen(snapshot.url).read()))

        print "downloading %s... done" % snapshot.url

        imunit = None
        for unit in fits:
            if unit.data is not None:
                imunit = unit

        img = imunit.data[:,:]
        imin, imax = np.min(img), np.max(img)
        rgbimg = np.repeat(((img - imin) / (imax - imin) * 255).astype(np.uint8), 3)

        def finish():
            h, w = img.shape
            surface = SDL_CreateRGBSurfaceFrom(rgbimg.ctypes.data, w, h, 24,
                                               3 * w, 0, 0, 0, 0)
            drawable_snapshots.append({'time': snapshot.time, 'surface': surface,
                                       'imgdata': rgbimg, 'window': window})
        run_on_main_thread(finish)

    collection=[]
    for window in windows: 
        collection.append(SnapshotCollection(window,
                                        lambda a: thpool.apply_async(put_up_snapshot, (a,window,))))

    time = 1421000000
    running = True
    event = SDL_Event()

    run_on_main_thread(lambda: None)

    while running:
        while SDL_WaitEvent(ctypes.byref(event)) != 0:
            if event.type == SDL_QUIT:
                running = False
                break

            if event.type == SDL_WINDOWEVENT_CLOSE:
                for i in range(0, WINDOWS): 
                    if event.window.windowID == window[i].windowID:
                        SDL_HideWindow(window[i])
                break


            if event.type == SDL_MOUSEWHEEL:
                time -= event.wheel.y * 50 * TIME_PER_PIX
                break

            if event.type == SDL_USEREVENT:
                if not main_thread_queue.empty():
                    while not main_thread_queue.empty():
                        main_thread_queue.get()()

                    break

        for window in collection: 
            window.cover(time - 800 * TIME_PER_PIX * 4,
                             time + 800 * TIME_PER_PIX * 5)

        for snapshot in drawable_snapshots:
            snapshot['window'].render(snaphot['surface'])

    for window in windows: 
        SDL_DestroyWindow(window)
    SDL_Quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())


