from nmigen import *

class LitexSoC(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        def request_compat(name, number):
            res = platform.lookup(name, number)
            return platform.request(
                name, number,
                dir={io.name: "-" for io in res.ios},
                xdr={io.name: 0   for io in res.ios},
            )

        uart      = request_compat("uart", 0)
        ddr3      = request_compat("ddr3", 0)
        eth_rgmii = request_compat("eth_rgmii", 0)

        m.submodules.soc = Instance("ecpix5",
            i_clk100        = ClockSignal("sync"),
            i_rst_n         = ~ResetSignal("sync"),

            i_serial_rx     = uart.rx,
            o_serial_tx     = uart.tx,

            o_ddram_a       = ddr3.a,
            o_ddram_ba      = ddr3.ba,
            o_ddram_ras_n   = ddr3.ras,
            o_ddram_cas_n   = ddr3.cas,
            o_ddram_we_n    = ddr3.we,
            o_ddram_dm      = ddr3.dm,
            i_ddram_dq      = ddr3.dq,
            i_ddram_dqs_p   = ddr3.dqs.p,
            o_ddram_clk_p   = ddr3.clk.p,
            o_ddram_cke     = ddr3.clk_en,
            o_ddram_odt     = ddr3.odt,

            o_eth_clocks_tx = eth_rgmii.tx_clk,
            i_eth_clocks_rx = eth_rgmii.rx_clk,
            o_eth_rst_n     = eth_rgmii.rst,
            i_eth_mdio      = eth_rgmii.mdio,
            o_eth_mdc       = eth_rgmii.mdc,
            i_eth_rx_ctl    = eth_rgmii.rx_ctrl,
            i_eth_rx_data   = eth_rgmii.rx_data,
            o_eth_tx_ctl    = eth_rgmii.tx_ctrl,
            o_eth_tx_data   = eth_rgmii.tx_data,
        )

        return m
