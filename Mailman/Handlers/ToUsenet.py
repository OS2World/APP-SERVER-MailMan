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

"""Inject the message to Usenet."""

import sys
import os
import time
import string
import re
import socket
import traceback
import errno

from Mailman import mm_cfg
from Mailman.Logging.Syslog import syslog
from Mailman.pythonlib.StringIO import StringIO



def process(mlist, msg, msgdata):
    # short circuits
    if not mlist.gateway_to_news or \
           msgdata.get('isdigest') or \
           msgdata.get('fromusenet'):
        return
    # sanity checks
    error = []
    if not mlist.linked_newsgroup:
        error.append('no newsgroup')
    if not mlist.nntp_host:
        error.append('no NNTP host')
    if error:
        syslog('error', 'NNTP gateway improperly configured: ' +
               string.join(error, ', '))
        return
    # Fork in case the nntp connection hangs.
    pid = os.fork()
    if pid:
        # In the parent.
        kids = msgdata.get('_kids', {})
        kids[pid] = pid
        msgdata['_kids'] = kids
        return
    # In the child
    try:
        do_child(mlist, msg)
        os._exit(0)
    except:
        traceback.print_exc()
        os._exit(1)



def do_child(mlist, msg):
    # The version we have is from Python 1.5.2+ and fixes the "mode reader"
    # problem.
    from Mailman.pythonlib import nntplib
    # Ok, munge headers, etc.
    subj = msg.getheader('subject')
    subjpref = mlist.subject_prefix
    if subj:
        if not re.match('(re:? *)?' + re.escape(subjpref), subj, re.I):
            msg['Subject'] = subjpref + subj
    else:
        msg['Subject'] = subjpref + '(no subject)'
    if mlist.reply_goes_to_list:
        del msg['reply-to']
        msg.headers.append('Reply-To: %s\n' % mlist.GetListEmail())
    # if we already have a sender header, don't add another one; use
    # the header that's already there.
    if not msg.getheader('sender'):
        msg.headers.append('Sender: %s\n' % mlist.GetAdminEmail())
    msg.headers.append('Errors-To: %s\n' % mlist.GetAdminEmail())
    msg.headers.append('X-BeenThere: %s\n' % mlist.GetListEmail())
    ngheader = msg.getheader('newsgroups')
    if ngheader is not None:
        # see if the Newsgroups: header already contains our
        # linked_newsgroup.  If so, don't add it again.  If not,
        # append our linked_newsgroup to the end of the header list
        ngroups = map(string.strip, string.split(ngheader, ','))
        if mlist.linked_newsgroup not in ngroups:
            ngroups.append(mlist.linked_newsgroup)
            ngheader = string.join(ngroups, ',')
            # subtitute our new header for the old one.  XXX Message
            # class should have a __setitem__()
            del msg['newsgroups']
            msg.headers.append('Newsgroups: %s\n' % ngroups)
    else:
        # Newsgroups: isn't in the message
        msg.headers.append('Newsgroups: %s\n' % mlist.linked_newsgroup)
    #
    # Note: We need to be sure two messages aren't ever sent to the same list
    # in the same process, since message ids need to be unique.  Further, if
    # messages are crossposted to two Usenet-gated mailing lists, they each
    # need to have unique message ids or the nntpd will only accept one of
    # them.  The solution here is to substitute any existing message-id that
    # isn't ours with one of ours, so we need to parse it to be sure we're not
    # looping.
    #
    # Our Message-ID format is <mailman.secs.pid.listname@hostname>
    msgid = msg.get('message-id')
    hackmsgid = 1
    if msgid:
        mo = re.search(
            msgid,
            r'<mailman.\d+.\d+.(?P<listname>[^@]+)@(?P<hostname>[^>]+)>')
        if mo:
            lname, hname = mo.group('listname', 'hostname')
            if lname == mlist.internal_name() and hname == mlist.host_name:
                hackmsgid = 0
    if hackmsgid:
        del msg['message-id']
        msg['Message-ID'] = '<mailman.%d.%d.%s@%s>' % (
            time.time(), os.getpid(), mlist.internal_name(), mlist.host_name)
    #
    # Lines: is useful
    if msg.getheader('Lines') is None:
        msg.headers.append('Lines: %s\n' % 
                           len(string.split(msg.body,"\n")))
    del msg['received']
    # TBD: Gross hack to ensure that we have only one
    # content-transfer-encoding header.  More than one barfs NNTP.  I
    # don't know why we sometimes have more than one such header, and it
    # probably isn't correct to take the value of just the first one.
    # What if there are conflicting headers???
    #
    # This relies on the new interface for getaddrlist() returning values
    # for all present headers, and the fact that the legal values are
    # usually not parseable as addresses.  Yes this is another bogosity.
    cteheaders = msg.getaddrlist('content-transfer-encoding')
    if cteheaders:
        ctetuple = cteheaders[0]
        ctevalue = ctetuple[1]
        del msg['content-transfer-encoding']
        msg['content-transfer-encoding'] = ctevalue
    # Here some headers that our NNTP server will simply outright reject.
    # These are hardcoded to what we know about INN, and other NNTP servers
    # may have different lists.  This will be configurable in MM2.1.
    #
    # We got this list of headers from two sources: from a post in
    # news.software.nntp describing the headers rejected by default in
    # nnrpd/post.c for INN, and in the logs/error file collected since early
    # 2000 on mail.python.org.
    for header in ('nntp-posting-host', 'x-trace', 'x-complaints-to',
                   'nntp-posting-date', 'xref', 'date-received',
                   'posted', 'posting-version', 'relay-version'):
        del msg[header]
    # INN will apparently complain if there are duplicates of any of these
    # headers.  That seems completely stupid on INN's part.  What choice do we
    # have?  In the interest of simplicity, we'll move all those to
    # X-Original-*: headers.
    for header in ('Cc', 'To'):
        headervals = msg.getaddrlist(header)
        del msg[header]
        newheader = 'X-Original-' + header + ': %s\n'
        for h, v in headervals:
            msg.headers.append(newheader % v)
    # NNTP is strict about spaces after the colon in headers.
    for n in range(len(msg.headers)):
        line = msg.headers[n]
        if line[0] in ' \t':
            # skip continuation lines
            continue
        i = string.find(line,":")
        if i <> -1 and line[i+1] <> ' ':
            msg.headers[n] = line[:i+1] + ' ' + line[i+1:]
    # flatten the message object, stick it in a StringIO object and post
    # that resulting thing to the newsgroup
    fp = StringIO(str(msg))
    conn = None
    try:
        try:
            conn = nntplib.NNTP(mlist.nntp_host, readermode=1,
                                user=mm_cfg.NNTP_USERNAME,
                                password=mm_cfg.NNTP_PASSWORD)
            conn.post(fp)
        except nntplib.error_temp, e:
            errmsg = '(ToUsenet) NNTP error for list "%s": %s' % (
                mlist.internal_name(), e)
            preserve_message(msg, errmsg)
        except socket.error, e:
            errmsg = '(ToUsenet) socket error for list "%s": %s' % (
                mlist.internal_name(), e)
            preserve_message(msg, errmsg)
    finally:
        if conn:
            conn.quit()


def preserve_message(msg, errmsg):
    # Preserve this message for possible reposting
    msgid = msg['message-id']
    # Set a useful header and log this failure
    msg['X-ToUsenet-Failure'] = errmsg
    syslog('error', errmsg)
    syslog('error', '(ToUsenet) Message-ID: %s' % msgid)
    path = os.path.join(mm_cfg.VAR_PREFIX, 'nntp')
    try:
        os.mkdir(path)
    except OSError, e:
        if e.errno <> errno.EEXIST: raise
    counter = 0
    filename = os.path.join(path, msgid + '.txt')
    while os.path.exists(filename):
        counter = counter + 1
        filename = os.path.join(path, msgid + '-%02d.txt' % counter)
    fp = open(filename, 'w')
    try:
        fp.write(str(msg))
    finally:
        fp.close()
