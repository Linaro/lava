FROM ubuntu:bionic

# Install telnet package
RUN apt-get update && \
    apt-get install --no-install-recommends --yes bc libatomic1 telnet libdbus-1-3 && \
    rm -rf /var/cache/apt

# Create model directory
RUN mkdir /opt/model

# Add FVP Binaries
# This example is for the free Foundation model.
# Download this by going to:
# https://developer.arm.com/tools-and-software/simulation-models/fixed-virtual-platforms
# Then find link under:
# "Armv8-A Foundation Platform"
# "Fast Models 11.9 (Linux)"
ADD FastModel_Download.tgz /opt/model

# Install the model
RUN cd /opt/model && \
    /opt/model/Foundation_Platform.sh \
        --i-agree-to-the-contained-eula \
        --verbose \
        --destination /opt/model/Foundation_Platformpkg
