# Trusted by

LAVA is the backbone of hardware testing for some of the world's most important
open-source projects. The organizations below rely on LAVA to validate their
code on real physical hardware or emulated platforms (QEMU, FVP).

<style>
.grid > div:hover img { opacity: 0.3; }
.grid > div:hover > div[style*="position: absolute"] { opacity: 1 !important; }
.grid > div > div[style*="position: absolute"] {
  top: auto !important;
  bottom: 0.5rem !important;
  transform: translate(-50%, 0) !important;
}
</style>

## KernelCI — Linux kernel validation

KernelCI uses LAVA as its **primary backend** for automated Linux kernel
hardware testing. Every kernel patch that lands in mainline has likely been
validated by LAVA running on dozens of boards across the KernelCI labs network.

> As KernelCI continues to grow and mature, the complexity of managing
> hardware testing laboratories has become increasingly apparent. While we
> currently support LAVA as our primary backend, the community has expressed
> strong interest in expanding our capabilities.
>
> — [KernelCI Labs Working Group announcement](https://kernelci.org)

KernelCI's Labs Working Group was created specifically to strengthen the
LAVA integration and scale hardware testing across the Linux community.

## 10x Engineers — RISC-V CI

10x Engineers uses LAVA through their Cloud-V platform for automated firmware
and kernel testing on RISC-V hardware. Their LAVA lab supports testing on
boards like StarFive VisionFive 2, SiFive HiFive Unleashed, Banana Pi F3,
Milk-V Jupiter, and Milk-V Pioneer Box.

## Android — pre-merge validation

LAVA tests proposed Android changes in Gerrit before they are landed, running
boot tests, VTS/CTS suites, and hardware compatibility checks on physical
Android development boards.

## Apertis — Debian-based IoT platform testing

Apertis uses LAVA for integration testing and package testing of their
Debian-based IoT platform. They have a dedicated LAVA test shell distro
profile, use Robot Framework integrated on LAVA, and run complete test
automation on LAVA infrastructure for all their reference hardware.

Apertis developers can also submit personal LAVA jobs during development
to debug tests or verify changes before final integration.

## GCC — compiler validation

LAVA tests GCC compiler output on real hardware, validating that code
produced by GCC is correct and performs as expected across a wide range of
embedded and server processors.

## Linux kernel — daily validation

LAVA tests the Linux kernel on a range of supported boards every day. It
validates bootloader changes, kernel boot sequences, and system-level
functionality across multiple architectures.

## Qualcomm — Debian and Yocto image validation

Qualcomm uses LAVA to automatically test their Linux images on physical
Qualcomm development boards. Their CI pipeline integrates LAVA via GitHub
Actions, submitting test jobs, monitoring execution, and publishing results
back to their repositories.

---

## Supported by

LAVA is built and maintained by a global community of engineers from leading
technology companies. The organizations below are the testimony of LAVA's
success.

## Core contributors

These organizations account for the vast majority of LAVA's codebase:

<div class="grid" style="grid-template-columns: repeat(2, 1fr); gap: 1.5rem; margin: 2rem 0;">

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/linaro.svg" alt="Linaro" width="160" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Linaro</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/collabora.svg" alt="Collabora" width="128" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Collabora</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/debian.svg" alt="Debian" width="64" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Debian</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/canonical.svg" alt="Canonical" width="128" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Canonical</div>
</div>

</div>

## Hardware partners

Major semiconductor and hardware companies:

<div class="grid" style="grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin: 2rem 0;">

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/nxp.svg" alt="NXP" width="64" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">NXP</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/baylibre.svg" alt="BayLibre" width="128" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">BayLibre</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/arm.svg" alt="ARM" width="64" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">ARM</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/qualcomm.svg" alt="Qualcomm" width="128" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Qualcomm</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/pengutronix.svg" alt="Pengutronix" width="128" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Pengutronix</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/renesas.svg" alt="Renesas" width="128" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Renesas</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/st.svg" alt="STMicroelectronics" width="128" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">STMicroelectronics</div>
</div>

<div style="text-align: center; padding: 1.5rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/ti.svg" alt="Texas Instruments" width="160" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Texas Instruments</div>
</div>

</div>

## Additional contributors and users

<div class="grid" style="grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 2rem 0;">

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/ubuntu.svg" alt="Ubuntu" width="48" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Ubuntu</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/foundriesio.svg" alt="Foundries.io" width="160" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Foundries.io</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/amd.svg" alt="AMD" width="64" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">AMD</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/amlogic.svg" alt="Amlogic" width="96" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Amlogic</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/cypress.svg" alt="Cypress" width="96" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Cypress</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/fairphone.svg" alt="Fairphone" width="96" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Fairphone</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/siemens.svg" alt="Siemens" width="96" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Siemens</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/linuxfoundation.svg" alt="Linux Foundation" width="96" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Linux Foundation</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/realtek.svg" alt="Realtek" width="128" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Realtek</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/hitachi.svg" alt="Hitachi Energy" width="96" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Hitachi Energy</div>
</div>

<div style="text-align: center; padding: 1rem; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 8px; position: relative;">
<img src="../assets/images/logos/se.svg" alt="Schneider Electric" width="96" style="cursor: pointer;">
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0; transition: opacity 0.2s; font-weight: 500; font-size: 0.9rem; pointer-events: none;">Schneider Electric</div>
</div>

</div>
