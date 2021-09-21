from nmigen import *
from nmigen.hdl.ast import Rose

from .i2c import I2CInitiator


__all__ = ["DVITester"]


class _AxisTiming:
    def __init__(self, visible, front, sync, back):
        self.visible = visible
        self.front = front
        self.sync = sync
        self.back = back
        self.whole = visible+front+sync+back


class VideoTiming:
    def __init__(self, width, height, framerate):
        # TODO: calculate video timing according to the given resolution
        # this is XGA@60fps
        self.h = _AxisTiming(1024, 24, 136, 160)
        self.v = _AxisTiming(768, 3, 6, 29)


class SyncGenerator(Elaboratable):
    """
    Note: this module assumes running at PCLK
    """
    def __init__(self, timing):
        if not isinstance(timing, VideoTiming):
            raise TypeError("Object {!r} is not a VideoTiming object".format(timing))
        self.timing = timing

        self.hsync = Signal()
        self.vsync = Signal()
        self.de = Signal()
        self.x = Signal(range(self.timing.h.visible))
        self.y = Signal(range(self.timing.v.visible))

    def elaborate(self, platform):
        m = Module()

        hcounter = Signal(range(self.timing.h.whole))
        vcounter = Signal(range(self.timing.v.whole))

        with m.If(hcounter != self.timing.h.whole-1):
            m.d.sync += hcounter.eq(hcounter+1)
        with m.Else():
            m.d.sync += hcounter.eq(0)

        with m.If(hcounter == self.timing.h.whole-1):
            with m.If(vcounter != self.timing.v.whole-1):
                m.d.sync += vcounter.eq(vcounter+1)
            with m.Else():
                m.d.sync += vcounter.eq(0)

        startsynch = self.timing.h.visible+self.timing.h.front
        stopsynch = self.timing.h.visible+self.timing.h.front+self.timing.h.sync

        startsyncv = self.timing.v.visible+self.timing.v.front
        stopsyncv = self.timing.v.visible+self.timing.v.front+self.timing.v.sync

        m.d.comb += [
            self.de.eq((hcounter < self.timing.h.visible) & (vcounter < self.timing.v.visible)),
            self.hsync.eq((hcounter >= startsynch) & (hcounter < stopsynch)),
            self.vsync.eq((vcounter >= startsyncv) & (vcounter < stopsyncv)),
            self.x.eq(hcounter[0:self.x.width]),
            self.y.eq(vcounter[0:self.y.width]),
        ]

        return m


class I2CInitializer(Elaboratable):
    def __init__(self, cmdpairs, pads):
        self.cmdpairs = cmdpairs
        self.pads = pads
        self.done = Signal()

    def elaborate(self, platform):
        m = Module()

        i2c = I2CInitiator(self.pads, 1000)
        m.submodules += i2c

        with m.FSM():
            for i in range(len(self.cmdpairs)):
                # Wait until busy=0
                with m.State("{}-Wait-Busy-Init".format(i)):
                    with m.If(~i2c.busy):
                        m.next = "{}-Start".format(i)

                # Send start for 1 cycle
                with m.State("{}-Start".format(i)):
                    m.d.comb += i2c.start.eq(1)
                    m.next = "{}-Wait-Start".format(i)

                # Wait until busy = 0
                with m.State("{}-Wait-Start".format(i)):
                    m.d.comb += i2c.start.eq(0)
                    with m.If(~i2c.busy):
                        m.next = "{}-Write-Slave-Addr".format(i)

                # Write slave address
                with m.State("{}-Write-Slave-Addr".format(i)):
                    m.d.comb += [
                        i2c.write.eq(1),
                        i2c.data_i.eq(self.cmdpairs[i][0] << 1),
                    ]
                    m.next = "{}-Wait-Write-Slave-Addr".format(i)

                # Wait until busy = 0
                with m.State("{}-Wait-Write-Slave-Addr".format(i)):
                    m.d.comb += i2c.write.eq(0)
                    with m.If(~i2c.busy):
                        m.next = "{}-Write-Reg-Addr".format(i)

                # Write register address
                with m.State("{}-Write-Reg-Addr".format(i)):
                    m.d.comb += [
                        i2c.write.eq(1),
                        i2c.data_i.eq(self.cmdpairs[i][1]),
                    ]
                    m.next = "{}-Wait-Write-Reg-Addr".format(i)

                # Wait until busy = 0
                with m.State("{}-Wait-Write-Reg-Addr".format(i)):
                    m.d.comb += i2c.write.eq(0)
                    with m.If(~i2c.busy):
                        m.next = "{}-Write-Reg-Val".format(i)

                # Write register value
                with m.State("{}-Write-Reg-Val".format(i)):
                    m.d.comb += [
                        i2c.write.eq(1),
                        i2c.data_i.eq(self.cmdpairs[i][2]),
                    ]
                    m.next = "{}-Wait-Write-Reg-Val".format(i)

                # Wait until busy = 0
                with m.State("{}-Wait-Write-Reg-Val".format(i)):
                    m.d.comb += i2c.write.eq(0)
                    with m.If(~i2c.busy):
                        m.next = "{}-Send-Stop".format(i)

                # Send stop for 1 cycle
                with m.State("{}-Send-Stop".format(i)):
                    m.d.comb += i2c.stop.eq(1)
                    m.next = "{}-Wait-Stop".format(i)

                # Wait until busy = 0
                with m.State("{}-Wait-Stop".format(i)):
                    m.d.comb += i2c.stop.eq(0)
                    if i == len(self.cmdpairs)-1:
                        with m.If(~i2c.busy):
                            m.next = "Init-Done"
                    else:
                        m.next = "{}-Wait-Busy-Init".format(i+1)

            with m.State("Init-Done"):
                m.d.comb += self.done.eq(1)

        return m

class TestCardGen(Elaboratable):
    def __init__(self, width, height, depth=12):
        self.width = width
        self.height = height

        self.i_de = Signal()
        self.i_hsync = Signal()
        self.i_vsync = Signal()
        self.x = Signal(range(self.width))
        self.y = Signal(range(self.height))

        self.o_de = Signal()
        self.o_hsync = Signal()
        self.o_vsync = Signal()

        self.r = Signal(depth)
        self.g = Signal(depth)
        self.b = Signal(depth)

    def sendColor(self, m, color):
        m.d.sync += [
            self.r.eq(color[0]),
            self.g.eq(color[1]),
            self.b.eq(color[2]),
        ]

    def elaborate(self, platform):
        m = Module()

        # Sync buffering
        m.d.sync += [
            self.o_de.eq(self.i_de),
            self.o_hsync.eq(self.i_hsync),
            self.o_vsync.eq(self.i_vsync),
        ]

        counter = Signal(6)
        with m.If(Rose(self.i_vsync)):
            m.d.sync += counter.eq(counter+1)

        # Colors
        bkg_grid = (0x600, 0x600, 0x600)
        frg_grid = (0xFFF, 0xFFF, 0xFFF)

        # Geometry
        grid = 50
        linewidth = 5

        # Calculate positions relative to the center
        x_rel = Signal(Shape(width=self.x.width+1, signed=True))
        y_rel = Signal(Shape(width=self.y.width+1, signed=True))
        m.d.comb += [
            x_rel.eq(self.x - self.width//2),
            y_rel.eq(self.y - self.height//2),
        ]

        # Radius is 80% of the smallest dimension of the screen
        radius = int(min(self.width, self.height) * 0.8 / 2)

        with m.If(self.i_de):
            with m.If(x_rel*x_rel+y_rel*y_rel <= radius*radius):
                self.sendColor(m, (0xF01, 0X394, 0XF39))
            with m.Else():
                with m.If((self.x[0:6] == counter) | (self.y[0:6] == counter)):
                    self.sendColor(m, frg_grid)
                with m.Else():
                    self.sendColor(m, bkg_grid)
        with m.Else():
            self.sendColor(m, (0,0,0))

        return m


class DVITester(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        hdmi = platform.request("it6613e", 0)

        # I2C control
        # This is pretty much the vanilla init sequence from
        # the CAT6613/IT6613E Programming Guide
        cat6613addr = 0x98 >> 1 # convert to a 7-bit addr
        cmds = [
            (cat6613addr, 0x04, 0x20), # Reset everything
            (cat6613addr, 0x04, 0x00), # Clear reset
            (cat6613addr, 0x61, 0x10), # Enable "clock ring"
            (cat6613addr, 0xF8, 0xFF), # Dunno
            (cat6613addr, 0x09, 0xFF), # Disable IRQs (0x09-0x0B)
            (cat6613addr, 0x0A, 0xFF),
            (cat6613addr, 0x0B, 0xFF),
            (cat6613addr, 0x0C, 0xFF), # Clear interrupts (0x0C-0x0D)
            (cat6613addr, 0x0D, 0xFF),
            (cat6613addr, 0xC0, 0x00), # DVI mode
            (cat6613addr, 0xC1, 0x03), # Mute screen
            (cat6613addr, 0xC6, 0x03),
            # TODO: match register choice with PCLK value
            (cat6613addr, 0x61, 0x03), # REG_DRV_PDRXDET | REG_DRV_TERMON
            (cat6613addr, 0x62, 0x18), # REG_XP_ER0 | REG_XP_RESETB
            (cat6613addr, 0x63, 0x10), # todo: document
            (cat6613addr, 0x64, 0x04), # todo: document
            (cat6613addr, 0xC1, 0x00), # Unmute screen
        ]
        i2cinit = I2CInitializer(cmds, hdmi)
        m.submodules += i2cinit

        # Video signal
        timing = VideoTiming(1024, 768, 60)
        syncgen = SyncGenerator(timing)
        m.submodules += syncgen
        m.d.comb += [
            hdmi.rst.eq(1),
            hdmi.pclk.eq(ClockSignal("sync")),
        ]

        # Test card generation
        tcgen = TestCardGen(1024, 768)
        m.submodules += tcgen
        m.d.comb += [
            tcgen.i_de.eq(syncgen.de),
            tcgen.i_hsync.eq(syncgen.hsync),
            tcgen.i_vsync.eq(syncgen.vsync),
            tcgen.x.eq(syncgen.x),
            tcgen.y.eq(syncgen.y),

            hdmi.hsync.eq(tcgen.o_hsync),
            hdmi.vsync.eq(tcgen.o_vsync),
            hdmi.de.eq(tcgen.o_de),
            hdmi.rst.eq(0),

            # Each color channel is 12-bits wide on ECPIX5-85, 8 on ECPIX5-45.
            hdmi.d.r.eq(tcgen.r[-len(hdmi.d.r):]),
            hdmi.d.g.eq(tcgen.g[-len(hdmi.d.g):]),
            hdmi.d.b.eq(tcgen.b[-len(hdmi.d.b):]),
        ]

        return m
