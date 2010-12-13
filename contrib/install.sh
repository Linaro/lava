#!/bin/bash
export LANG=C

function get_deps() {
    echo "Inspecting your system to determine dependencies"
    
    case "$(lsb_release -i -s)" in
        Ubuntu)
        ;;
        
        *)
        echo "Your distribution is not supported"
        exit 1
        ;;
    esac

    case "$(lsb_release -r -s)" in
        10.04)
        SERVER_PKGS="python-django python-docutils python-simplejson"
        CLIENT_PKGS="python-argparse"
        TEST_PKGS="python-testscenarios python-setuptools python-coverage"
        ;;
        
        *)
        echo "This release of ubuntu is not supported"
        exit 1
    esac
}

function get_yes_no() {
    local question="$1"
    local default="${2:-y}"
    local answer
    while [ "x$answer" != "xy" -a "x$answer" != "xn" ]; do
        read -p "$question [y/n, default $default] " answer
        if [ "x$answer" = "x" ]; then
            answer="$default"
        fi
    done
    echo $answer
}


function install_deps() {
    get_deps

    if [ "$(get_yes_no "Do you want to install dependencies for the server?")" = "y" ]; then
        PKGS="$PKGS $SERVER_PKGS"
    fi
    if [ "$(get_yes_no "Do you want to install dependencies for the client?")" = "y" ]; then
        PKGS="$PKGS $CLIENT_PKGS"
    fi
    if [ "$(get_yes_no "Do you want to install dependencies for the test suite?")" = "y" ]; then
        PKGS="$PKGS $TEST_PKGS"
    fi

    echo "About to install the following packages"
    IFS=" "
    for pkg in $PKGS; do
        echo " * $pkg"
    done
    go=$(get_yes_no "Is this correct?" n)

    if [ "$go" = "y" ]; then
        sudo apt-get install $PKGS
    fi
}


function main() {
    echo "This script will help you to install launch-control on your system"
    echo "Currently it can only install the required dependencies"

    if [ "$(get_yes_no "Do you want to continue?")" != "y" ]; then
        exit
    fi
    
    install_deps

}


main

