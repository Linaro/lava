// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Cgroup device allowlist for sharing host devices with docker containers
 * under cgroups v2. Compiled ahead of time (libbpf/CO-RE style): the
 * lava-dispatcher-host daemon loads this object with bpftool and fills the
 * map, so no kernel headers or clang are needed at runtime.
 */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

/*
 * Wildcard minor for "major only" entries (e.g. 136:* for /dev/pts/N).
 * dev_t minors are 20 bits wide, so this value can never collide with a
 * real minor.
 */
#define ANY_MINOR 0xFFFFFFFFu

struct dev_key {
	__u32 major;
	__u32 minor;
};

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	/* Ceiling: DEFAULT entries (10) + devices shared with one container.
	 * Beyond this, a map update fails and apply() aborts (fail-closed). */
	__uint(max_entries, 256);
	__type(key, struct dev_key);
	__type(value, __u32);
} allowed_devices SEC(".maps");

SEC("cgroup/device")
int lava_docker_device_access_control(struct bpf_cgroup_dev_ctx *ctx)
{
	struct dev_key key = { .major = ctx->major, .minor = ctx->minor };

	if (bpf_map_lookup_elem(&allowed_devices, &key))
		return 1;
	key.minor = ANY_MINOR;
	return bpf_map_lookup_elem(&allowed_devices, &key) ? 1 : 0;
}

char LICENSE[] SEC("license") = "GPL";
