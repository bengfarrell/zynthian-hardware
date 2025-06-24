#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai MPD218"
# ******************************************************************************

import logging

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyngine.ctrldev.zynthian_ctrldev_base_extended import CONST

from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# --------------------------------------------------------------------------
# 'Akai MPD218' device controller class
#
# This controller, so far, is really just for pad/sequence launching.
# It should work in any Zynthian state as I want this to work relatively headless
# There might be some value in making a different mode going for the pattern editor,
# as this device is a drum pad and could work well.
#
# For pattern/pad launching, this assumes you're using a 4x4 grid as that's
# the actual pad configuration on the hardware.
# Tapping a pad will toggle the playback state of the sequence
# The dials on the left of the device will map to volumes for each bank(?).
#
# On this device, both the CTRL and PAD banks can be set (A, B, or C).
# In this fashion, the pads notes will change. So instead of launching
# pads 1-16, you may launch pads 17-32, or 33-48 by selecting B and C banks
#
# Likewise with the dials. Bank 1-6 volumes are in CTRL bank A, but 7-12, or 13-18
# can be controlled with banks B and C
#
# Also, I REALLY wanted a scene launcher. Something that triggers all pads
# across the column you've triggered. So, hit the pad, but hold it, and apply max
# pressure to the pad. The pressure sensitivity of the device, once at max, will
# use the last note hit. The play state of this pad and the 3 pads next will be
# set to playing. I'm not really sure how well this interaction will feel, but it's...something!
# --------------------------------------------------------------------------
class zynthian_ctrldev_akai_mpd_218(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = ["MPD218 IN 1"]

    def __init__(self, state_manager, idev_in, idev_out=None):
        super().__init__(state_manager, idev_in, idev_out)

    PAD_BANK_A_NOTE_PAD_START = 36
    PAD_BANK_B_NOTE_PAD_START = 52
    PAD_BANK_C_NOTE_PAD_START = 68

    PAD_BANK_A_NOTE_PAD_END = 51
    PAD_BANK_B_NOTE_PAD_END = 67
    PAD_BANK_C_NOTE_PAD_END = 83

    CTRL_BANK_A_NOTE_DIAL_START = 3 # goes from 3 to 9 to 12, then 13, 14, 15
    CTRL_BANK_B_NOTE_DIAL_START = 16
    CTRL_BANK_C_NOTE_DIAL_START = 22

    CTRL_BANK_A_NOTE_DIAL_END = 15
    CTRL_BANK_B_NOTE_DIAL_END = 21
    CTRL_BANK_C_NOTE_DIAL_END = 27

    CC_PRESSURE = 10

    MIN_DIAL = 0
    MIN_PRESSURE = 0
    MAX_DIAL = 127
    MAX_PRESSURE = 127

    PADS_IN_ROW = 4
    PADS_IN_COLUMN = 4

    currentNotePressed = -1

    def init(self):
        self.sleep_off()

    @classmethod
    def get_autoload_flag(cls):
        return True

    def get_note_xy(self, note):
        note_start_offset = 0
        bank = ""
        if self.PAD_BANK_A_NOTE_PAD_START <= note <= self.PAD_BANK_A_NOTE_PAD_END:
            bank = "A"
            note_start_offset = self.PAD_BANK_A_NOTE_PAD_START

        if self.PAD_BANK_B_NOTE_PAD_START <= note <= self.PAD_BANK_B_NOTE_PAD_END:
            bank = "B"
            note_start_offset = self.PAD_BANK_B_NOTE_PAD_START

        if self.PAD_BANK_C_NOTE_PAD_START <= note <= self.PAD_BANK_C_NOTE_PAD_END:
            bank = "C"
            note_start_offset = self.PAD_BANK_C_NOTE_PAD_START

        # pads go left to right, but top to bottom
        # pads are also returned 0 index based
        row = 4 - ((note - note_start_offset) // self.PADS_IN_ROW) - 1
        col = ((note - note_start_offset) % self.PADS_IN_COLUMN)
        return col, row, bank

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        note = ev[1] & 0x7F
        velocity = ev[2] & 0x7F
        channel = ev[0] & 0x0F

        #logging.debug("MPD218 Midi Event => {}".format(ev))
        if evtype == CONST.MIDI_NOTE_ON:
            self.note_on(note, channel, velocity)
        elif evtype == CONST.MIDI_NOTE_OFF:
            self.note_off(note, channel)
        elif evtype == CONST.MIDI_CC:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            self.cc_change(ccnum, ccval)
        elif evtype == 0xD:
            self.pressureChange(channel, note)

    def note_on(self, note, channel, velocity):
        #logging.debug("MPD218 Note on handler => {}".format(note))
        col, row, bank = self.get_note_xy(note)
        self.currentNotePressed = note
        pad = self.zynseq.get_pad_from_xy(col, row)
        if pad >= 0:
            self.zynseq.libseq.togglePlayState(self.zynseq.bank, pad)
            return True

    def note_off(self, note, channel):
        #logging.debug("MPD218 Note off handler => {}".format(note))
        self.currentNotePressed = -1

    def pressureChange(self, channel, pressure):
        #logging.debug("MPD218 Set pressure for channel {} to {} ".format(channel, pressure))
        # Pressure event comes in on channel 9 (for any note held I guess)

        #logging.debug("MPD218 Check if we hard pressed to launch a scene {} - {} - {}".format(pressure, self.MAX_PRESSURE, self.currentNotePressed))
        if pressure == self.MAX_PRESSURE:
            logging.debug("Start scene for pads {} through {} ".format(self.currentNotePressed, self.currentNotePressed + 3))
            self.zynseq.libseq.setPlayState(self.zynseq.bank, self.currentNotePressed, 0)
            self.zynseq.libseq.setPlayState(self.zynseq.bank, self.currentNotePressed + 1, 0)
            self.zynseq.libseq.setPlayState(self.zynseq.bank, self.currentNotePressed + 2, 0)
            self.zynseq.libseq.setPlayState(self.zynseq.bank, self.currentNotePressed + 3, 0)

    def cc_change(self, ccnum, ccval):
        #logging.debug("MPD218 CC handler => {} - {}".format(ccnum, ccval))
        # We're probably fiddling with knobs
        # bank = ""
        mixer_channel = -1
        if self.CTRL_BANK_A_NOTE_DIAL_START <= ccnum <= self.CTRL_BANK_A_NOTE_DIAL_END:
            # bank = "A"
            if ccnum == 3: mixer_channel = 0
            if ccnum == 9: mixer_channel = 1
            if ccnum == 12: mixer_channel = 2
            if 13 <= ccnum <= self.CTRL_BANK_A_NOTE_DIAL_END: mixer_channel = ccnum - self.CTRL_BANK_A_NOTE_DIAL_START

        if self.CTRL_BANK_B_NOTE_DIAL_START <= ccnum <= self.CTRL_BANK_B_NOTE_DIAL_END:
            # bank = "B"
            # Mixer will have many inputs past the 6 in bank A - repurpose this bank for something else?
            mixer_channel = ccnum - self.CTRL_BANK_B_NOTE_DIAL_START

        if self.CTRL_BANK_C_NOTE_DIAL_START <= ccnum <= self.CTRL_BANK_C_NOTE_DIAL_END:
            # bank = "C"
            # Mixer will have many inputs past the 6 in bank A - repurpose this bank for something else?
            mixer_channel = ccnum - self.CTRL_BANK_C_NOTE_DIAL_START

        #logging.debug("MPD218 Set volume for channel {} to {} ".format(mixer_channel, ccval // self.MAX_DIAL))
        if mixer_channel > -1:
            self.zynmixer.set_level(mixer_channel, ccval / self.MAX_DIAL)


    #def update_seq_state(self, bank, seq, state=None, mode=None, group=None):
    #logging.debug("MPD218 State {}, {}, {}, {} ".format(bank, seq, state, mode))
