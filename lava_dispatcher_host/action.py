from lava_dispatcher_host import add_device_container_mapping


class DeviceContainerMappingMixin:
    """
    This mixing should be included by action classes that add device/container
    mappings.
    """

    def add_device_container_mappings(self, container, container_type):
        device_info = self.job.device.get("device_info", [])
        job_id = self.job.job_id
        job_prefix = self.job.parameters["dispatcher"].get("prefix", "")
        devices = []
        for origdevice in device_info:
            device = origdevice.copy()
            if "board_id" in device:
                device["serial_number"] = device["board_id"]
                del device["board_id"]
            devices.append(device)
        for device in devices:
            add_device_container_mapping(
                job_prefix + job_id, device, container, container_type=container_type
            )
