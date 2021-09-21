from nmigen import *
from usb_protocol.emitters import DeviceDescriptorCollection

from luna.gateware.platform.ecpix5 import *
from luna.gateware.usb.usb2.device import USBDevice


__all__ = ["USBTestDevice"]


class USBTestDevice(Elaboratable):
    def create_descriptors(self):
        descriptors = DeviceDescriptorCollection()

        with descriptors.DeviceDescriptor() as d:
            d.idVendor           = 0x16d0
            d.idProduct          = 0xf3b
            d.iManufacturer      = "LUNA"
            d.iProduct           = "Test Device"
            d.iSerialNumber      = "1234"
            d.bNumConfigurations = 1

        with descriptors.ConfigurationDescriptor() as c:
            with c.InterfaceDescriptor() as i:
                i.bInterfaceNumber = 0

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x01
                    e.wMaxPacketSize   = 64

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x81
                    e.wMaxPacketSize   = 64

        return descriptors

    def elaborate(self, platform):
        m = Module()

        m.domains.usb = ClockDomain("usb")

        bus = platform.request(platform.default_usb_connection)
        m.submodules.usb = usb = USBDevice(bus=bus, handle_clocking=True)

        descriptors = self.create_descriptors()
        usb.add_standard_control_endpoint(descriptors)

        m.d.comb += [
            usb.connect.eq(1),
            usb.full_speed_only.eq(0),
        ]

        return m
