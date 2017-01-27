#!/usr/bin/i386/python2.7
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
"""finalizer_rollback - Rollback the state of a distro build """

import sys
import osol_install.distro_const.dc_checkpoint as dc_ckp 
from osol_install.distro_const.dc_utils import setup_dc_logging

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Rollback the state of a distro build

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object
        (not used)

  PKG_IMG_MNT_PT: Package image area mountpoint (not used)

  TMP_DIR: Temporary directory to contain the boot archive file (not used)

  BA_BUILD: Area where boot archive is put together (not used)

  MEDIA_DIR: Area where the media is put (not used)

  ZFS_SNAPSHOTS (variable number): List of snapshots to take as part of this
        checkpoint operation

  MESSAGE: Message to print while checkpointing

"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
LENGTH = len(sys.argv)

if LENGTH < 8:
    raise Exception, (sys.argv[0] + ": At least 9 args are required:\n" +
                      "Reader socket, pkg_image area, tmp area, boot archive"
                      "build area,\n" + "media area, zfs dataset(s), message")

ZFS_SNAPSHOTS = sys.argv[6:LENGTH-1]
MESSAGE = sys.argv[LENGTH-1]

DC_LOG = setup_dc_logging()

for snapshot in ZFS_SNAPSHOTS:
    dc_ckp.shell_cmd("/usr/sbin/zfs rollback -r " + snapshot, DC_LOG)

DC_LOG.info(MESSAGE)

sys.exit(0)
