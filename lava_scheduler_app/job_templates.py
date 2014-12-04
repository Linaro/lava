DEFAULT_TEMPLATE = {
    "job_name": "JOBNAME_PARAMETER",
    "device_type": "DEVICE_TYPE_PARAMETER",
    "tags": "TAGS_PARAMETER",
    "timeout": "TIMEOUT_PARAMETER",
    "logging_level": "DEBUG",
    "notify_on_incomplete": "NOTIFY_ON_INCOMPLETE_PARAMETER",
    "actions": "ACTIONS_PARAMETER"
}

ACTIONS_LINARO = [
    {
        "command": "DEPLOY_COMMAND_PARAMETER",
        "parameters": "DEPLOY_PARAMETER",
    },
    "COMMAND_TEST_SHELL",
    "COMMAND_SUBMIT_RESULTS"
]

ACTIONS_LINARO_BOOT = [
    {
        "command": "DEPLOY_COMMAND_PARAMETER",
        "parameters": "DEPLOY_PARAMETER",
    },
    {
        "command": "boot_linaro_image",
        "parameters": {
            "boot_cmds": "BOOT_OPTIONS_PARAMETER",
        }
    },
    "COMMAND_TEST_SHELL",
    "COMMAND_SUBMIT_RESULTS"
]

DEPLOY_IMAGE = {
    "image": "PREBUILT_IMAGE_PARAMETER"
}

DEPLOY_IMAGE_HWPACK = {
    "hwpack": "HWPACK_PARAMETER",
    "rootfs": "ROOTFS_PARAMETER"
}

DEPLOY_IMAGE_KERNEL = {
    "kernel": "KERNEL_PARAMETER",
    "ramdisk": "RAMDISK_PARAMETER",
    "dtb": "DTB_PARAMETER",
    "rootfs": "ROOTFS_PARAMETER"
}

LAVA_TEST_SHELL_REPO = {
    "testdef_repos": [
        {
            "git-repo": "REPO_PARAMETER",
            "testdef": "TESTDEF_PARAMETER"
        }
    ]
}

LAVA_TEST_SHELL_URL = {
    "testdef_urls": "TESTDEF_URLS_PARAMETER"
}

COMMAND_SUBMIT_RESULTS = {
    "command": "submit_results",
    "parameters": {
        "server": "SUBMIT_SERVER",
        "stream": "BUNDLE_STREAM"
    }
}

COMMAND_TEST_SHELL = {
    "command": "lava_test_shell",
    "parameters": "TEST_SHELL_PARAMETER",
}

ACTIONS_LINARO_ANDROID_IMAGE = [
    {
        "command": "deploy_linaro_android_image",
        "parameters": {
            "boot": "BOOT_IMAGE_PARAMETER",
            "data": "DATA_IMAGE_PARAMETER",
            "system": "SYSTEM_IMAGE_PARAMETER"
        }
    },
    {
        "command": "android_install_binaries"
    },
    "ANDROID_BOOT",
    {
        "command": "lava_android_test_install",
        "parameters": {
            "tests": "TESTS_PARAMETER"
        }
    },
    {
        "command": "lava_android_test_run",
        "parameters": {
            "test_name": "TEST_NAME_PARAMETER"
        }
    },
    "COMMAND_SUBMIT_RESULTS"
]

ANDROID_BOOT_NO_CMDS = {
    "command": "boot_linaro_android_image",
}

ANDROID_BOOT_WITH_CMDS = {
    "command": "boot_linaro_android_image",
    "parameters": {
        "boot_cmds": "ANDROID_BOOT_OPTIONS_PARAMETER"
    }
}
