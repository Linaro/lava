FROM ubuntu:bionic

# Install telnet package
RUN apt-get -yq update && \
	apt-get -yq install telnet && \
	rm -rf /var/cache/apt

# Create model directory
RUN mkdir /opt/model

# Add FVP Binaries
# This example is for the free Foundation model.
# Download this by going to:
# https://developer.arm.com/tools-and-software/simulation-models/fixed-virtual-platforms
# Then find link under:
# "Armv8-A Foundation Platform"
# "Fast Models 11.8 (Linux)"
ADD FastModel_Download.tgz /opt/model
