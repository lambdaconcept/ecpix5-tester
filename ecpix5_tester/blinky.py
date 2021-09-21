import itertools

from nmigen import *
from nmigen.build import *


__all__ = ["Blinky"]


def get_all_resources(platform, name):
    resources = []
    for number in itertools.count():
        try:
            resources.append(platform.request(name, number))
        except ResourceError:
            break
    return resources


class Blinky(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        rgb_leds = [res for res in get_all_resources(platform, "rgb_led")]
        rgb_sel  = Record([("r", 1), ("g", 1), ("b", 1)])
        rgb_sel.r.reset = 1
        leds     = [res.o for res in get_all_resources(platform, "led")]

        sd_card = platform.request("sd_card", 0)
        m.d.comb += [
            sd_card.sel.o     .eq(0), # 3.3V
            sd_card.dir_dat123.eq(1), # output
            sd_card.dir_dat0  .eq(1), # output
            sd_card.dir_cmd   .eq(1), # output
        ]
        leds += [
            sd_card.cmd.o,
            sd_card.clk.o,
            sd_card.dat0.o, sd_card.dat1.o, sd_card.dat2.o, sd_card.dat3.o,
        ]

        clk_freq = platform.default_clk_frequency
        timer    = Signal(range(int(clk_freq//4)), reset=int(clk_freq//4) - 1)
        led_en   = Signal()

        for i, rgb_led in enumerate(rgb_leds):
            m.d.comb += [
                rgb_led.r.o.eq(led_en & rgb_sel.r),
                rgb_led.g.o.eq(led_en & rgb_sel.g),
                rgb_led.b.o.eq(led_en & rgb_sel.b),
            ]

        m.d.comb += Cat(leds).eq(~Repl(led_en, len(leds)))

        with m.If(timer == 0):
            m.d.sync += [
                timer.eq(timer.reset),
                led_en.eq(~led_en),
            ]
            with m.If(led_en):
                m.d.sync += rgb_sel.eq(Cat(rgb_sel[-1], rgb_sel[:-1]))
        with m.Else():
            m.d.sync += timer.eq(timer - 1)

        return m
