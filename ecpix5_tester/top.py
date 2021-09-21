from nmigen import *
from nmigen.build import *
from luna.gateware.platform.ecpix5 import *

from .blinky import Blinky
from .dvi import DVITester
from .usb import USBTestDevice
from .soc import LitexSoC

from importlib import import_module, resources
from . import litex


class CRG(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        clk100_i   = Signal()
        m.d.comb += clk100_i.eq(platform.request("clk100").i)

        m.domains.pixel = ClockDomain("pixel")
        m.domains.sync  = ClockDomain("sync")

        pll_locked = Signal()
        pll_clkfb  = Signal()

        m.submodules.pll = Instance("EHXPLLL",
            a_ICP_CURRENT            = "12",
            a_LPF_RESISTOR           = "8",
            a_MFG_ENABLE_FILTEROPAMP = "1",
            a_MFG_GMCREF_SEL         = "2",
            p_PLLRST_ENA             = "DISABLED",
            p_INTFB_WAKE             = "DISABLED",
            p_STDBY_ENABLE           = "DISABLED",
            p_DPHASE_SOURCE          = "DISABLED",
            p_OUTDIVIDER_MUXA        = "DIVA",
            p_OUTDIVIDER_MUXB        = "DIVB",
            p_OUTDIVIDER_MUXC        = "DIVC",
            p_OUTDIVIDER_MUXD        = "DIVD",

            a_FREQUENCY_PIN_CLKI     = "100",
            p_CLKI_DIV               = 20,
            i_CLKI                   = clk100_i,

            a_FREQUENCY_PIN_CLKOP    = "65",
            p_CLKOP_ENABLE           = "ENABLED",
            p_CLKOP_DIV              = 9,
            p_CLKOP_CPHASE           = 4,
            p_CLKOP_FPHASE           = 0,
            o_CLKOP                  = ClockSignal("pixel"),

            p_FEEDBK_PATH            = "INT_OP",
            p_CLKFB_DIV              = 13,
            i_CLKFB                  = pll_clkfb,
            o_CLKINTFB               = pll_clkfb,

            i_RST                    = Const(0),
            i_STDBY                  = Const(0),
            i_PHASESEL0              = Const(0),
            i_PHASESEL1              = Const(0),
            i_PHASEDIR               = Const(1),
            i_PHASESTEP              = Const(1),
            i_PHASELOADREG           = Const(1),
            i_PLLWAKESYNC            = Const(0),
            i_ENCLKOP                = Const(0),
            o_LOCK                   = pll_locked,
        )

        m.d.comb += [
            ClockSignal("sync").eq(clk100_i),
            ResetSignal("sync").eq(platform.request("rst", 0).i),
        ]

        return m


class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()
        m.submodules.crg    = CRG()
        m.submodules.blinky = Blinky()
        m.submodules.dvi    = DomainRenamer("pixel")(DVITester())
        m.submodules.usb    = USBTestDevice()
        m.submodules.soc    = LitexSoC()
        return m


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("85", "45"), default="85",
        help="platform variant (default: %(default)s)")

    args = parser.parse_args()
    if args.variant == "85":
        platform = ECPIX5_85F_Platform()
    else:
        platform = ECPIX5_45F_Platform()

    platform.add_resources([
        Resource("sd_card", 0,
            Subsignal("cmd",        Pins("M24", dir="o")),
            Subsignal("clk",        Pins("P24", dir="o")),
            Subsignal("cd",         Pins("L22", dir="o")),
            Subsignal("dat0",       Pins("N26", dir="o")),
            Subsignal("dat1",       Pins("N25", dir="o")),
            Subsignal("dat2",       Pins("N23", dir="o")),
            Subsignal("dat3",       Pins("N21", dir="o")),
            Subsignal("sel",        Pins("L24", dir="o")),
            Subsignal("clk_fb",     Pins("J26", dir="i")),
            Subsignal("dir_dat123", Pins("P26", dir="o")),
            Subsignal("dir_dat0",   Pins("N24", dir="o")),
            Subsignal("dir_cmd",    Pins("M23", dir="o")),
            Attrs(IO_TYPE="LVCMOS33"),
        ),
    ])

    # Add PMODs as user LEDs
    for pmod_number in range(8):
        platform.add_resources([
            *[Resource("led", pmod_number * 8 + pin_number,
                Pins(pin_name, dir="o", conn=("pmod", pmod_number)),
                Attrs(IO_TYPE="LVCMOS33")
            ) for pin_number, pin_name in enumerate(["1", "2", "3", "4", "7", "8", "9"])],

            # Last pin selects the second 7-segment digit
            Resource("led", pmod_number * 8 + 7,
                PinsN("10", dir="o", conn=("pmod", pmod_number)),
                Attrs(IO_TYPE="LVCMOS33")
            ),
        ])

    # Add LiteX SoC files
    platform.add_file("Ram_1w_1rs_Generic.v", resources.read_text(litex, "Ram_1w_1rs_Generic.v"))
    platform.add_file("VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ood_Wm.v", resources.read_text(litex, "VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ood_Wm.v"))
    platform.add_file("mem.init",   resources.read_text(litex, "mem.init"))
    platform.add_file("mem_1.init", resources.read_text(litex, "mem_1.init"))
    platform.add_file("mem_2.init", resources.read_text(litex, "mem_2.init"))
    platform.add_file("ecpix5.v",   resources.read_text(litex, "ecpix5.v"))

    platform.build(Top(), do_program=True)
