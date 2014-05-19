$(document).ready(function () {

    function JobWizard(element) {
        this.element = element;
        this.settings = JobWizard.prototype.SETTINGS;
    }

    JobWizard.prototype.start = function() {

        $(this.element).validate(JobWizard.prototype.VALIDATION_RULES);
        this.add_validation();
        $(this.element).steps(this.settings);
        this.interactive();
    }

    JobWizard.prototype.interactive = function() {

        $("#boot_type").change(function(event) {
            if ($(this).val() == "linaro_image") {
                $("#image_url_container").show();
                $("#hwpack_container").hide();
                $("#rootfs_container").hide();
                $("#android_boot_container").hide();
                $("#android_data_container").hide();
                $("#android_system_container").hide();
                $("#kernel_container").hide();
                $("#ramdisk_container").hide();
                $("#dtb_container").hide();
                $("#kernel_rootfs_container").hide();
            } else if ($(this).val() == "linaro_hwpack") {
                $("#image_url_container").hide();
                $("#hwpack_container").show();
                $("#rootfs_container").show();
                $("#android_boot_container").hide();
                $("#android_data_container").hide();
                $("#android_system_container").hide();
                $("#kernel_container").hide();
                $("#ramdisk_container").hide();
                $("#dtb_container").hide();
                $("#kernel_rootfs_container").hide();
            } else if ($(this).val() == "linaro_kernel") {
                $("#image_url_container").hide();
                $("#hwpack_container").hide();
                $("#rootfs_container").hide();
                $("#android_boot_container").hide();
                $("#android_data_container").hide();
                $("#android_system_container").hide();
                $("#kernel_container").show();
                $("#ramdisk_container").show();
                $("#dtb_container").show();
                $("#kernel_rootfs_container").show();
            } else {
                $("#image_url_container").hide();
                $("#hwpack_container").hide();
                $("#rootfs_container").hide();
                $("#android_boot_container").show();
                $("#android_data_container").show();
                $("#android_system_container").show();
                $("#kernel_container").hide();
                $("#ramdisk_container").hide();
                $("#dtb_container").hide();
                $("#kernel_rootfs_container").hide();
            }
        });
        $("#boot_type").change();

        $("#testdef_type").change(function(event) {
            if ($(this).val() == "repo") {
                $("#repo_container").show();
                $("#testdef_container").show();
                $("#testdef_url_container").hide();
                $("#test_name_container").hide();
            } else {
                $("#repo_container").hide();
                $("#testdef_container").hide();
                $("#testdef_url_container").show();
                $("#test_name_container").hide();
            }
        });
        $("#testdef_type").change();

        $("#submit_stream").autocomplete({
            source: "/dashboard/streams/bundlestreams-json",
            minLength: 2,
        });
    }

    JobWizard.prototype.add_validation = function() {

        $.validator.addMethod("source_url",function(value) {
            match =
                value.match(/(http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?/) ||
                value.match(/^file:\/\/\/[a-z0-9-\.]+/) ||
                value.match(/^scp:\/\/[a-z0-9-\.]+\@[a-z0-9-\.]+\:[a-z0-9-\.\/]+/);
            return match;
        }, "Please enter a valid path (http://, file:/// or scp://).");

        $.validator.classRuleSettings.source_url = { source_url: true };

        $.validator.addMethod("repo_url",function(value) {
            match =
                value.match(/^((https?|git|bzr):\/\/[a-z0-9-\.]+\.[a-z]{2,4}\/?([^\s<>\#%"\,\{\}\\|\\\^\[\]`]+)?)?$/);
            return match;
        }, "Please enter a valid repo path (git, bzr or http).");

        $.validator.classRuleSettings.repo_url = { repo_url: true };

        object = this;
        this.settings["onStepChanging"] = function(event, currentIndex, newIndex) {

            if (newIndex == 2) {
                if ($("#boot_type").val() == "android_image") {
                    $("#testdef_type_container").hide();
                    $("#repo_container").hide();
                    $("#testdef_container").hide();
                    $("#testdef_url_container").hide();
                    $("#test_name_container").show();
                } else {
                    $("#testdef_type_container").show();
                    $("#test_name_container").hide();
                    $("#testdef_type").change();
                }
            }

            $(object.element).validate().settings.ignore = ":disabled,:hidden";
            return $(object.element).valid();
        };
    }

    JobWizard.prototype.SETTINGS = {
        headerTag: "h1",
        bodyTag: "fieldset",
        cssClass: "wizard",
        stepsOrientation: $.fn.steps.stepsOrientation.horizontal,

        titleTemplate: '<span class="number">#index#.</span> #title#',
        loadingTemplate: '<span class="spinner"></span> #text#',

        autoFocus: false,
        enableAllSteps: false,
        enableKeyNavigation: true,
        enablePagination: true,
        suppressPaginationOnFocus: true,
        enableContentCache: true,
        enableFinishButton: true,
        preloadContent: false,
        showFinishButtonAlways: false,
        forceMoveForward: false,
        saveState: false,
        startIndex: 0,

        transitionEffect: "slideLeft",
        transitionEffectSpeed: 200,

        onStepChanging: function (event, currentIndex, newIndex) {
            return true;
        },
        onFinishing: function (event, currentIndex) {
            return true;
        },
        onFinished: function (event, currentIndex) {
            var form = $(this);
            form.submit();
        },

        labels: {
            finish: "Finish",
            next: "Next",
            previous: "Previous",
            loading: "Loading ..."
        }
    };

    JobWizard.prototype.VALIDATION_RULES = {
        errorPlacement: function (error, element)
        {
            element.before(error);
        }
    };


    wizard = new JobWizard($("#job_wizard"));
    wizard.start();

});
