#
# PyDBG
# Copyright (C) 2006 Pedram Amini <pedram.amini@gmail.com>
#
# $Id: system_dll.py 238 2010-04-05 20:40:46Z rgovostes $
#
# This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program; if not, write to the Free
# Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#

'''
@author:       Pedram Amini
@license:      GNU General Public License 2.0 or later
@contact:      pedram.amini@gmail.com
@organization: www.openrce.org
'''

from __future__ import print_function

import os.path

from my_ctypes import *
from defines   import *
from windows_h import *

# macos compatability.
try:
    kernel32 = windll.kernel32
    psapi    = windll.psapi
except:
    kernel32 = CDLL(os.path.join(os.path.dirname(__file__), "libmacdll.dylib"))
    psapi    = kernel32

from pdx import *

import os

import ctypes
from ctypes import wintypes
GetMappedFileNameA = ctypes.windll.psapi.GetMappedFileNameA
LPSTR = POINTER(CHAR)
GetMappedFileNameA.argtypes = (wintypes.HANDLE, wintypes.LPVOID, LPSTR, wintypes.DWORD)
GetMappedFileNameA.restype = wintypes.BOOL
#  HANDLE hProcess,
#  LPVOID lpv,
#  LPSTR  lpFilename,
#  DWORD  nSize

CreateFileMappingA = ctypes.windll.kernel32.CreateFileMappingA
LPSTR = POINTER(CHAR)
CreateFileMappingA.argtypes = (wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, LPSTR)
CreateFileMappingA.restype = wintypes.HANDLE
#HANDLE CreateFileMappingA(
#  HANDLE                hFile,
#  LPSECURITY_ATTRIBUTES lpFileMappingAttributes,
#  DWORD                 flProtect,
#  DWORD                 dwMaximumSizeHigh,
#  DWORD                 dwMaximumSizeLow,
#  LPCSTR                lpName
#);



class system_dll:
    '''
    System DLL descriptor object, used to keep track of loaded system DLLs and locations.

    @todo: Add PE parsing support.
    '''

    handle = None
    base   = None
    name   = None
    path   = None
    pe     = None
    size   = 0

    ####################################################################################################################
    def __init__ (self, handle, base):
        '''
        Given a handle and base address of the loaded DLL, determine the DLL name and size to fully initialize the
        system DLL object.

        @type  handle: HANDLE
        @param handle: Handle to the loaded DLL
        @type  base:   DWORD
        @param base:   Loaded address of DLL

        @raise pdx: An exception is raised on failure.
        '''

        self.handle = handle
        self.base   = base
        self.name   = None
        self.path   = None
        self.pe     = None
        self.size   = 0

        # calculate the file size of the
        file_size_hi = c_ulong(0)
        file_size_lo = 0
        file_size_lo = kernel32.GetFileSize(handle, byref(file_size_hi))
        self.size    = (file_size_hi.value << 8) + file_size_lo

        # create a file mapping from the dll handle.
        # CreateFileMappingA.argtypes = (wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, LPSTR)
        file_map = kernel32.CreateFileMappingA(handle, c_void_p(0), c_ulong(PAGE_READONLY), c_ulong(0), c_ulong(1), b"")

        if file_map:
            # map a single byte of the dll into memory so we can query for the file name.
            kernel32.MapViewOfFile.restype = POINTER(c_char)
            file_ptr = kernel32.MapViewOfFile(file_map, FILE_MAP_READ, 0, 0, 1)

            if file_ptr:
                # query for the filename of the mapped file.
                filename = create_string_buffer(2048)
                # ctypes.ArgumentError: argument 1: <type 'exceptions.OverflowError'>: long int too long to convert
                # psapi.GetMappedFileNameA(kernel32.GetCurrentProcess(), file_ptr, byref(filename), 2048)
                print("BEFORE GetMappedFileNameA")
                #psapi.GetMappedFileNameA(kernel32.GetCurrentProcess(), file_ptr, byref(filename), c_ulong(2048))
                psapi.GetMappedFileNameA(kernel32.GetCurrentProcess(), file_ptr, filename, c_ulong(2048))
                print("AFTER GetMappedFileNameA")
                print("AFTER GetMappedFileNameA filename=", filename)

                # store the full path. this is kind of ghetto, but i didn't want to mess with QueryDosDevice() etc ...
                self.path = b"\\" + filename.value.split(b"\\", 3)[3]
                print("AFTER GetMappedFileNameA self.path=", self.path)

                # store the file name.
                # XXX - this really shouldn't be failing. but i've seen it happen.
                try:
                    self.name = filename.value[filename.value.rindex(os.sep)+1:]
                except:
                    self.name = self.path

                kernel32.UnmapViewOfFile(file_ptr)

            kernel32.CloseHandle(file_map)


    ####################################################################################################################
    def __del__ (self):
        '''
        Close the handle.
        '''

        kernel32.CloseHandle(self.handle)