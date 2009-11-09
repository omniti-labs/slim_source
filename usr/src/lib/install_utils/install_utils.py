#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

import sys
import os
import stat
import errno
import select
import string
from subprocess import *
from logging import *
from osol_install.transfer_defs import TRANSFER_ID
import osol_install.liblogsvc as logsvc

# =============================================================================
# =============================================================================
# Tracing section.
# =============================================================================
# =============================================================================

# =============================================================================
class Trace:
# =============================================================================
	"""Tracing facility.
	"""

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Constants
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	# Masks.  Add as needed, for different sections of the program.
	DEFVAL_MASK = 1<<0
	FINALIZER_MASK = 1<<1
	CHECKPOINT_MASK = 1<<2

	# Defaults.
	DEFAULT_LEVEL = 2
	DEFAULT_MASK = -1

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Classbound variables
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	master_level = DEFAULT_LEVEL
	master_mask = DEFAULT_MASK


	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	@staticmethod
	def set_mask(new_mask):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Set a new mask for log to use for comparison.

		Args:
		  new_mask: New mask.

		Returns: N/A

		Raises: None
		"""
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		Trace.master_mask = new_mask


	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	@staticmethod
	def set_level(new_level):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Set a new debug level for log to use for comparison.

		Args:
		  new_mask: New mask.

		Returns: N/A

		Raises: None
		"""
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		Trace.master_level = new_level

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	@staticmethod
	def log(level, mask, formatstr, varargs=()):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Log a tracing message if level is numerically low enough and
		at least one bit of mask is set in master_mask.

		Args:
		  level: int level (priority) to print message.  The lower the
			number, the greater the likelihood the message will
			print.  Use lowest numbers for messages which always
			need to print, higher numbers for more detailed messages
			which are desired less frequently.

		  mask: bitmask used to categorize the message.  If message
			category isn't also set in the master_mask, the message
			won't print.

		  formatstr: format string, same as first arg to print.

		  varargs: tuple of args to pass to print after the format
			string and the subsequent "%" operator.  Defaults to an
			empty tuple if not provided.
		"""
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		if ((level <= Trace.master_level) and
		    ((mask & Trace.master_mask) != 0)):
			print formatstr % varargs


#==============================================================================
#==============================================================================
# Code used to parse an input string.  If no unescaped quotes or double-quotes
# are seen in the string, the whole string is returned in one token.  Quotes or 
# double-quotes enveloping tokens break the input into the enveloped tokens.
# Quotes and double-quotes can be escaped with a \.  Unescaped quotes can be
# used inside double-quotes, and vice versa.
#
# Examples:
#   abc		-> [ abc ]		"abc" "def"	-> [ abc, def ]
#   "abc"	-> [ abc ]		"a'bc" "d\"ef"	-> [ a'bc, d"ef ]
#   abc def	-> [ abc, def ]		'a"bc' 'd\'ef'	-> [ a"bc, d'ef ]
#   "abc def"	-> [ abc def ]		"abc def" "ghi"	-> [ abc def, ghi ]
#   "a'b'c" 'd"e"f ghi'	-> [ a'b'c, d"e"f ghi ]
#==============================================================================
#==============================================================================

# States
(
__qst_start,		# Start
__qst_char,		# Most chars and whitespace
__qst_esc,		# escape (first backslash character)
__qst_sqt,		# Unescaped single quote
__qst_dqt		# Unescaped double quote
) = range(5)

# State table indices.
(
__qst_nonesc,		# Index used by start, char, sqt and dqt states
__qst_bsesc		# Index used by esc state
) = range(2)

# Next state indices.  These correspond to the current char which determines
# the next state.
(
__qst_char_char,	# Index in the tables corresp to char or whtsp recd
__qst_char_bs,		# Index in the tables corresp to a backslash recd
__qst_char_sqt,		# Index in the tables corresp to a single quote recd
__qst_char_dqt		# Index in the tables corresp to a double quote recd
) = range(4)

# The state table

__qst_nonesc_tbl = []
__qst_nonesc_tbl.insert(__qst_char_char, __qst_char)
__qst_nonesc_tbl.insert(__qst_char_bs, __qst_esc)
__qst_nonesc_tbl.insert(__qst_char_sqt, __qst_sqt)
__qst_nonesc_tbl.insert(__qst_char_dqt, __qst_dqt)

__qst_esc_tbl = []
__qst_esc_tbl.insert(__qst_char_char, __qst_char)
__qst_esc_tbl.insert(__qst_char_bs, __qst_char)
__qst_esc_tbl.insert(__qst_char_sqt, __qst_char)
__qst_esc_tbl.insert(__qst_char_dqt, __qst_char)

__space_state_table = []
__space_state_table.insert(__qst_nonesc, __qst_nonesc_tbl)
__space_state_table.insert(__qst_bsesc, __qst_esc_tbl)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __space_next_state(curr_state, curr_char):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Find next state from space state table.  (Private function)
# 
# Args:
#   curr_state: Current state.  One of the state table states listed above
#
#   curr_char: Current character.
#
# Returns: Next state.  One of the state table states listed above.
#
# Raises: N/A
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	if (curr_state == __qst_esc):
		idx = __qst_bsesc
	else:
		idx = __qst_nonesc
	if (curr_char == "\""):
		next_state = __space_state_table[idx][__qst_char_dqt]
	elif (curr_char == "\'"):
		next_state = __space_state_table[idx][__qst_char_sqt]
	elif (curr_char == "\\"):
		next_state = __space_state_table[idx][__qst_char_bs]
	else:
		next_state = __space_state_table[idx][__qst_char_char]
	return next_state


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def space_parse(input):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Parse an input string into words, accounting for whitespace
	inside quoted (or double-quoted) strings.

	Quotes and double-quotes can be escaped with a \.  Unescaped quotes
	can be used inside double-quotes, and vice versa.

	Unescaped quotes and double-quotes are removed from the output.

	Escaped quotes and double-quotes are added to the output but their
	escaping \ are removed.

	Args:
	  input: string to parse.

	Returns: list of parsed tokens.

	Raises: N/A
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Initialize.
	state = __qst_start
	word = ""
	outlist = []
	squoteon = False
	dquoteon = False
	input = input.strip()

	# Examine each character individually.
	for char in input:
		next_state = __space_next_state(state, char)

		# If previous state was escape and current char isn't a quote
		# being escaped, treat the previous backslash as a normal
		# character and append to the current word.
		if ((state == __qst_esc) and
		    ((char != "\"") and (char != "'"))):
			word += "\\"

		# Regular character
		if (next_state == __qst_char):
			word += char

		# Escaped single quote
		elif (next_state == __qst_sqt):
			if (dquoteon):
				word += char
			else:
				squoteon = not squoteon
				if (not squoteon):
					if (len(word) != 0):
						outlist.append(word.strip())
						word = ""
		
		# Escaped double quote
		elif (next_state == __qst_dqt):
			if (squoteon):
				word += char
			else:
				dquoteon = not dquoteon
				if (not dquoteon):
					if (len(word) != 0):
						outlist.append(word.strip())
						word = ""

		elif (next_state != __qst_esc):
			print >>sys.stderr, (
			    "space_parse: Shouldn't get here!!!! " +
			    "Char:%s, state:%d, next:%d" % (char, state,
			    next_state))

		state = next_state

	# Done looping.  Handle the case of residual mismatched quotes or
	# double-quotes.
	if ((squoteon) or (dquoteon)):
		raise Exception, "Unexpected unescaped quote found: " + input

	# Handle the case where the \ is the last character of the input.
	if (state == __qst_esc):
		word += "\\"

	# Flush any remaining word in progress.
	if (len(word) != 0):
		outlist.append(word.strip())

	return (outlist)


# =============================================================================
# =============================================================================
# Other utility functions
# =============================================================================
# =============================================================================

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def isnumber(arg):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Public function: does the (string) argument represent a number
	Hex, octal, decimal, floating point are all considered.
	Malformed numbers are considered not numeric.

	Test cases:
	  0x123, .123, 0x.1, 0x0x123, 12.2, 12..3, 12.,  1.2.3, 1.23, 12z4, abc,
	  0xabc, 0x1a2b3c4, 0xa2b3c4d, 0xabcdefg, 0xgabcdef, 0x123.

	Args:
	  String value to evaluate

	Returns:
	  True: string represents a number.
	  False: string does not represent a numeric value.

	Raises: None
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	try:
		dummy = int(arg, 0)
		return True
	except ValueError:
		pass
	try:
		dummy = float(arg)
		return True
	except ValueError:
		pass
	return False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def canaccess(filename, mode):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Test to see if can access filename with "mode" permissions

	If the file exists and can be accessed, just return.  Otherwise, throw
	an exception which contains appropriate errno value for proper error
	message.

	This method is needed because the chosen XML validator doesn't
	return an appropriate errno for its exit status, so file access needs
	to be checked independently.

	Args:
	  filename: Name of the file to test for access

	  mode: Character string mode, r=read, w=write, rw=read/write

	Returns: N/A

	Raises:
	  IOError with the appropriate errno: file doesn't exist or doesn't
		have the permissions required for the requested access.
	  IOError with errno = EINVAL: mode argument is invalid
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	# Don't try opening file with mode "w", else file will be truncated.
	if (mode == "rw"):
		mode = "a+"
	elif (mode == "w"):
		mode = "a"
	elif (mode != "r"):
		raise IOError, (errno.EINVAL, os.strerror(errno.EINVAL) +
		    ": " + "mode")

	dummy = os.stat(filename)		# Check for file existance.
	dummy = open(filename, mode)		# Check for file permissions.
	dummy.close()				# Clean up if you get here.


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def exec_cmd_outputs_to_log(cmd, log,
                            stdout_log_level=None, stderr_log_level=None,
                            discard_stdout=False):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Executes the given command and sends the stdout and stderr to log
	files.

	Args:
	  cmd: The command to execute.  The cmd is expected to have a suitable
	       format for calling Popen with shell=False, ie: the command and
	       its arguments should be in an array.
	  stdout_log_level: Logging level for the stdout of each command.  If
               not specified, it will default to DEBUG
	  stderr_log_level: Logging level for the stderr of each command.  If
               not specified, it will default to ERROR
	  discard_stdout: If set to True, discard stdout

	Returns:
	  The return value of the command executed.

	Raises: None
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	if (stdout_log_level == None):
		stdout_log_level = DEBUG
	
	if (stderr_log_level == None):
		stderr_log_level = ERROR

	#
	# number of bytes to read at once.  There's no particular
	# reason for picking this number, just pick a bigger
	# value so we don't need to have multiple reads for large output
	#
	buf_size=8192

	# log pkg(1) command to be invoked along with all parameters
	if log is not None:
		log.log(stdout_log_level, "pkg cmd: " + string.join(cmd))
	else:
		logsvc.write_log(TRANSFER_ID,
				 "pkg cmd: " + string.join(cmd) + "\n")

	p = Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=PIPE,
	    shell=False, close_fds=True)
	(child_stdout, child_stderr) = (p.stdout, p.stderr)

	out_fd = child_stdout.fileno()
	err_fd = child_stderr.fileno()

	#
	# Some commands produce multiple output messages on the same line.
	# For those cases, we don't want to log the output we read immediately
	# because it will destroy the original formatting of the output
	# and make it difficult to read. We use two 
	# buffers to store output or error from commands.  We will
	# only write a log record for them when we get a trailing newline 
	# on the output/error
	#
	stdout_buf = ""
	stderr_buf = ""
	fl_cmd_finished = False

	while not fl_cmd_finished:
		ifd, ofd, efd = select.select([out_fd, err_fd], [], [])

		if err_fd in ifd:
			# something available from stderr of the command
			output = os.read(err_fd, buf_size)

			# Store the output we just read in the buffer.
			# Examine the buffer and if it contains whole lines,
			# extract and log them right now, so that smooth
			# progress report from invoked command is provided.
			stderr_buf = stderr_buf + output

			if not output:
				fl_cmd_finished = True

			while string.find(stderr_buf, "\n") != -1:
				new_line_pos = string.find(stderr_buf, "\n")

				if log is not None:
					log.log(stderr_log_level,
					        stderr_buf[0:new_line_pos])
				else:
					logsvc.write_dbg(TRANSFER_ID,
				                 logsvc.LS_DBGLVL_ERR,
				                 stderr_buf[0:new_line_pos + 1])

				stderr_buf = stderr_buf[new_line_pos + 1:]

			# Process has terminated - no more data to be read.
			# Write the rest of the buffer
			if fl_cmd_finished and len(stderr_buf) > 0:
				if log is not None:
					log.log(stderr_log_level, stderr_buf)
				else:
					logsvc.write_dbg(TRANSFER_ID,
					                 logsvc.LS_DBGLVL_ERR,
					                 stderr_buf + "\n")

		if out_fd in ifd:
			# something available from stdout of the command
			output = os.read(out_fd, buf_size)

			if not output:
				fl_cmd_finished = True
		
			# if stdout is to be discarded, skip the logging step
			if discard_stdout:
				continue

			# Store the output we just read in the buffer.
			# Examine the buffer and if it contains whole lines,
			# extract and log them right now, so that smooth
			# progress report from invoked command is provided.
			stdout_buf = stdout_buf + output

			while string.find(stdout_buf, "\n") != -1:
				new_line_pos = string.find(stdout_buf, "\n")

				if log is not None:
					log.log(stdout_log_level,
					        stdout_buf[0:new_line_pos])
				else:
					logsvc.write_log(TRANSFER_ID,
				                 stdout_buf[0:new_line_pos + 1])

				stdout_buf = stdout_buf[new_line_pos + 1:]

			# Process has terminated - no more data to be read.
			# Write the rest of the buffer
			if fl_cmd_finished and len(stdout_buf) > 0:
				if log is not None:
					log.log(stdout_log_level, stdout_buf)
				else:
					logsvc.write_log(TRANSFER_ID,
					                 stdout_buf + "\n")

	return (p.wait())


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __find_error_handler(raise_me):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Error handler for find() below.  Raises the exception passed to it.

	Args:
	  raise_me: Exception to raise

	Returns: None

	Raises: The exception passed in.
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	raise raise_me


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def find(rootpaths, type=None, raise_errors=False):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Python implementation of the Unix find(1) command.

	Order of output is similar, but not the same as, find(1) when -depth
	is not passed to it.  A directory is enumerated before the files it
	contains.

	Unlike find(1), no errors are returned when given a file or directory
	to parse which doesn't exist (when raise_errors is False)

	Args:
	  rootpaths: list of file and/or directory pathnames to parse.

	  type:
		- When set to None, return all found pathnames.
		- When set to "dir", return all found directories only.  This
			does not include links to directories.
		- When set to "file", return all found files only.  This does
			not include links to files.

	 raise_errors:
		- When set to True: raise an OSError when a non-existant file
			or directory to parse is passed in the rootpaths list.
		- When set to False, ignore any such errors.
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	rlist = []
	error_handler = None

	if ((type != None) and (type != "dir") and (type != "file")):
		raise Exception, (
		    "find: \"type\" must be None, \"dir\" or \"file\"")

	if (raise_errors):
		error_handler = __find_error_handler

	for rootpath in rootpaths:

		try:
			stat_out = os.lstat(rootpath)
		except OSError:		# Doesn't exist
			continue

		# Handle case where rootpath is not a proper directory.
		# (Links to directories are not proper directories.)
		if ((type == None) and (not stat.S_ISDIR(stat_out.st_mode))):
			rlist.append(rootpath)
			continue

		# Print rootpath only if a proper file, if type == "file"
		elif (type == "file"):
			if (stat.S_ISREG(stat_out.st_mode)):
				rlist.append(rootpath)
			continue

		for path, subdirs, files in os.walk(rootpath, True,
		    error_handler):

			# Take the path if we're taking everything, or if
			# type == dir and path is a proper directory (not link)
			if ((type == None) or
			    ((type == "dir") and
			    (stat.S_ISDIR(stat_out.st_mode)))):
				rlist.append(path)

			# Only the directory is desired.
			if (type == "dir"):
				continue

			# If names listed in subdirs are not directories (e.g.
			# they are symlinks), append them if type is None,
			# like what find(1) does.  If they are dirs, then
			# os.walk will get them on the next pass.
			if (type == None):
				for subdir in subdirs:
					fullname = path + "/" + subdir
					stat_out = os.lstat(fullname)
					if (not stat.S_ISDIR(stat_out.st_mode)):
						rlist.append(fullname)

			for file in files:
				fullname = path + "/" + file
				# Check for a proper file if (type == "file")
				if (type == "file"):
					stat_out = os.lstat(fullname)
					if (not stat.S_ISREG(stat_out.st_mode)):
						continue
				rlist.append(fullname)
	return rlist

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def file_size(filename):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""
	Get the size of the specified file/dir.

	If the size of a file/directory is not multiples of 1024, it's size
	will be rounded up to the next multiples of 1024.  This mimics the
	behavior of ufs especially with directories.  This results in a
	total size that's slightly bigger than if du was called on a ufs
	directory.

	The exception that will be raised by os.lstat() is intentionally
	not caught in this function so it can get passed to the caller
	and caller can deal with it.

	Args:
	  filename: name of the file or directory to get the size for
		
	Returns:
		size of the file or directory in bytes.

	Raises:
		None.

	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# os.path.getsize() can't be used
	# here because that call follows symlinks, which is not
	# what we want to do. Use os.lstat() so symlinks are not
	# followed
	stat = os.lstat(filename)

	if (stat.st_size % 1024 == 0):
		return stat.st_size
	else:
		return (((stat.st_size / 1024) + 1) * 1024)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def dir_size(rootpath):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Estimates the size of the given directory.

	This function is similar in functionality to the "du" command,
	but this function works for both ufs and zfs.  
	On UFS, du(1) reports the size of the data blocks within the file.
	On ZFS, du(1) reports the actual size of the file as stored on disk.
	This size includes metadata as well as compression.  So, given
	exactly the same content for a directory, du reports different
	sizes depending on whether the directory is on UFS or ZFS.

	This function will traverse all the directories/files under a
	given directory, and add up the sizes for all the directories and files,
	and return the value in bytes.  
	
	Args:
	  rootpath: root of the directory to calculate the size for

	Returns:
	  Size of the directory contents in bytes.
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	size = 0

	# Get the size of the root directory
	size += file_size(rootpath)
	if (size == 0):
		# This indicates the root directory is not valid
		raise Exception, (rootpath + "is not valid")

	for root, subdirs, files in os.walk(rootpath):
		# There's no need to distinguish between directories and
		# files in the size calculation, merge the subdirs list
		# and files list to make rest of the code simpler.
		for f in (files + subdirs):
			filename = root + "/" + f
			try:
				size += file_size(filename)
			except:
				# No need to exit because can't get size of
				# a file/dir, just print an error and continue
				print >> sys.stderr, \
				    ("Error getting information about "
				    + filename)
				continue

	return (size)
