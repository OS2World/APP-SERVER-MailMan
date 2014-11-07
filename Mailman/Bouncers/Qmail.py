# Copyright (C) 1998,1999,2000 by the Free Software Foundation, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software 
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""Parse bounce messages generated by qmail.

Qmail actually has a standard, called QSBMF (qmail-send bounce message
format), as described in

    http://cr.yp.to/proto/qsbmf.txt

This module should be conformant.

"""

import string
import re

introtag = 'Hi. This is the'

acre = re.compile(r'<(?P<addr>[^>]*)>:')



def process(msg):
    msg.rewindbody()
    # simple state machine
    #    0 = nothing seen yet
    #    1 = intro paragraph seen
    #    2 = recip paragraphs seen
    state = 0
    addrs = []
    while 1:
        line = msg.fp.readline()
        if not line:
            break
        line = string.strip(line)
        if state == 0 and line[:len(introtag)] == introtag:
            state = 1
        elif state == 1 and not line:
            state = 2
        elif state == 2:
            if line and line[0] == '-':
                # we're looking at the break paragraph, so we're done
                break
            # At this point we know we must be looking at a recipient
            # paragraph
            mo = acre.match(line)
            if mo:
                addrs.append(mo.group('addr'))
            # otherwise, it must be a continuation line, so just ignore it
        # not looking at anything in particular
    #
    # we've parse everything we need to
    return addrs or None