# -*- coding: utf-8 -*-
"""
  monotonic
  ~~~~~~~~~

  This module provides a ``monotonic()`` function which returns the
  value (in fractional seconds) of a clock which never goes backwards.

  On Python 3.3 or newer, ``monotonic`` will be an alias of
  ``time.monotonic`` from the standard library. On older versions,
  it will fall back to an equivalent implementation:

  +-------------+--------------------+
  | Linux, BSD  | clock_gettime(3)   |
  +-------------+--------------------+
  | Windows     | GetTickCount64     |
  +-------------+--------------------+
  | OS X        | mach_absolute_time |
  +-------------+--------------------+

  If no suitable implementation exists for the current platform,
  attempting to import this module (or to import from it) will
  cause a RuntimeError exception to be raised.


  Copyright 2014 Ori Livneh <ori@wikimedia.org>

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

"""
import ctypes
import ctypes.util
import os
import platform
import re
import sys
import time


__all__ = ('monotonic',)


def get_os_release():
    """Get the leading numeric component of the OS release."""
    return re.match('[\d.]+', platform.release()).group(0)


def compare_versions(v1, v2):
    """Compare two version strings."""
    def normalize(v):
        return map(int, re.sub(r'(\.0+)*$', '', v).split('.'))
    return cmp(normalize(v1), normalize(v2))


try:
    monotonic = time.monotonic
except AttributeError:
    try:
        if sys.platform == 'darwin':  # OS X, iOS
            # See Technical Q&A QA1398 of the Mac Developer Library:
            #  <https://developer.apple.com/library/mac/qa/qa1398/>
            libc = ctypes.CDLL('/usr/lib/libc.dylib', use_errno=True)

            class mach_timebase_info_data_t(ctypes.Structure):
                """System timebase info. Defined in <mach/mach_time.h>."""
                _fields_ = (('numer', ctypes.c_uint32),
                            ('denom', ctypes.c_uint32))

            mach_absolute_time = libc.mach_absolute_time
            mach_absolute_time.restype = ctypes.c_uint64

            timebase = mach_timebase_info_data_t()
            libc.mach_timebase_info(ctypes.byref(timebase))
            ticks_per_second = timebase.numer / timebase.denom * 1.0e9

            def monotonic():
                """Monotonic clock, cannot go backward."""
                return mach_absolute_time() / ticks_per_second

        elif sys.platform.startswith('win32'):
            # Windows Vista / Windows Server 2008 or newer.
            GetTickCount64 = ctypes.windll.kernel32.GetTickCount64
            GetTickCount64.restype = ctypes.c_ulonglong

            def monotonic():
                """Monotonic clock, cannot go backward."""
                return GetTickCount64() / 1000.0

        elif sys.platform.startswith('cygwin'):
            # Cygwin
            kernel32 = ctypes.cdll.LoadLibrary('kernel32.dll')
            GetTickCount64 = kernel32.GetTickCount64
            GetTickCount64.restype = ctypes.c_ulonglong

            def monotonic():
                """Monotonic clock, cannot go backward."""
                return GetTickCount64() / 1000.0

        else:
            try:
                clock_gettime = ctypes.CDLL(ctypes.util.find_library('c'),
                                            use_errno=True).clock_gettime
            except AttributeError:
                clock_gettime = ctypes.CDLL(ctypes.util.find_library('rt'),
                                            use_errno=True).clock_gettime

            class timespec(ctypes.Structure):
                """Time specification, as described in clock_gettime(3)."""
                _fields_ = (('tv_sec', ctypes.c_long),
                            ('tv_nsec', ctypes.c_long))

            ts = timespec()

            if sys.platform.startswith('linux'):
                if compare_versions(get_os_release(), '2.6.28') > 0:
                    CLOCK_MONOTONIC = 4  # CLOCK_MONOTONIC_RAW
                else:
                    CLOCK_MONOTONIC = 1
            elif sys.platform.startswith('freebsd'):
                CLOCK_MONOTONIC = 4
            elif sys.platform.startswith('sunos5'):
                CLOCK_MONOTONIC = 4
            elif 'bsd' in sys.platform:
                CLOCK_MONOTONIC = 3

            def monotonic():
                """Monotonic clock, cannot go backward."""
                if clock_gettime(CLOCK_MONOTONIC, ctypes.pointer(ts)):
                    errno = ctypes.get_errno()
                    raise OSError(errno, os.strerror(errno))
                return ts.tv_sec + ts.tv_nsec / 1.0e9

        # Perform a sanity-check.
        if monotonic() - monotonic() > 0:
            raise ValueError('monotonic() is not monotonic!')

    except Exception:
        raise RuntimeError('no suitable implementation for this system')
