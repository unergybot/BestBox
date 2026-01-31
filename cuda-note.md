## CUDA Note

unergy@ryypol-16:~/.cache$ tree huggingface -L 2
huggingface
├── hub
│   ├── datasets--mozilla-foundation--common_voice_13_0
│   ├── models--BAAI--bge-m3
│   ├── models--BAAI--bge-reranker-base
│   ├── models--livekit--turn-detector
│   ├── models--Qwen--Qwen2.5-14B-Instruct
│   ├── models--Qwen--Qwen2.5-VL-3B-Instruct
│   ├── models--Qwen--Qwen3-ASR-0.6B
│   ├── models--Qwen--Qwen3-VL-8B-Instruct
│   ├── models--Systran--faster-distil-whisper-large-v3
│   ├── models--Systran--faster-distil-whisper-small.en
│   ├── models--Systran--faster-whisper-base.en
│   ├── models--Systran--faster-whisper-medium
│   ├── models--Systran--faster-whisper-small
│   ├── models--Systran--faster-whisper-tiny
│   └── models--unsloth--Qwen3-30B-A3B-Instruct-2507-GGUF
├── models--Qwen--Qwen2.5-14B-Instruct
│   ├── blobs
│   ├── refs
│   └── snapshots
└── xet
    ├── https___cas_serv-tGqkUaZf_CBPHQ6h
    └── logs

---
unergy@ryypol-16:~/BestBox$ tree third_party -L 2
third_party
├── llama.cpp
│   ├── AGENTS.md
│   ├── AUTHORS
│   ├── benches
│   ├── build
│   ├── build-xcframework.sh
│   ├── ci
│   ├── CLAUDE.md
│   ├── cmake
│   ├── CMakeLists.txt
│   ├── CMakePresets.json
│   ├── CODEOWNERS
│   ├── common
│   ├── CONTRIBUTING.md
│   ├── convert_hf_to_gguf.py
│   ├── convert_hf_to_gguf_update.py
│   ├── convert_llama_ggml_to_gguf.py
│   ├── convert_lora_to_gguf.py
│   ├── docs
│   ├── examples
│   ├── flake.lock
│   ├── flake.nix
│   ├── ggml
│   ├── gguf-py
│   ├── grammars
│   ├── include
│   ├── LICENSE
│   ├── licenses
│   ├── Makefile
│   ├── media
│   ├── models
│   ├── mypy.ini
│   ├── pocs
│   ├── poetry.lock
│   ├── pyproject.toml
│   ├── pyrightconfig.json
│   ├── README.md
│   ├── requirements
│   ├── requirements.txt
│   ├── scripts
│   ├── SECURITY.md
│   ├── src
│   ├── tests
│   ├── tools
│   └── vendor
├── piper
│   ├── espeak-ng
│   ├── espeak-ng-data
│   ├── libespeak-ng.so -> libespeak-ng.so.1
│   ├── libespeak-ng.so.1 -> libespeak-ng.so.1.52.0.1
│   ├── libespeak-ng.so.1.52.0.1
│   ├── libonnxruntime.so -> libonnxruntime.so.1.14.1
│   ├── libonnxruntime.so.1.14.1
│   ├── libpiper_phonemize.so -> libpiper_phonemize.so.1
│   ├── libpiper_phonemize.so.1 -> libpiper_phonemize.so.1.2.0
│   ├── libpiper_phonemize.so.1.2.0
│   ├── libtashkeel_model.ort
│   ├── piper
│   ├── piper_phonemize
│   └── pkgconfig
└── vllm
    ├── benchmarks
    ├── cmake
    ├── CMakeLists.txt
    ├── codecov.yml
    ├── CODE_OF_CONDUCT.md
    ├── CONTRIBUTING.md
    ├── csrc
    ├── DCO
    ├── docker
    ├── docs
    ├── examples
    ├── LICENSE
    ├── MANIFEST.in
    ├── mkdocs.yaml
    ├── pyproject.toml
    ├── README.md
    ├── RELEASE.md
    ├── requirements
    ├── SECURITY.md
    ├── setup.py
    ├── tests
    ├── tools
    ├── use_existing_torch.py
    └── vllm

37 directories, 49 files
unergy@ryypol-16:~/BestBox$ 


---
unergy@ryypol-16:~/BestBox$ tree models/
models/
└── piper
    ├── en_US-amy-low.onnx
    ├── en_US-amy-low.onnx.json
    ├── en_US-libritts_r-low.onnx
    ├── en_US-libritts_r-medium.onnx
    ├── en_US-libritts_r-medium.onnx.json
    ├── en_US-libritts_r.onnx
    ├── zh_CN-huayan-medium.onnx
    └── zh_CN-huayan-medium.onnx.json

2 directories, 8 files
unergy@ryypol-16:~/BestBox$ 

---
unergy@ryypol-16:~/BestBox$ docker images
                                                            i Info →   U  In Use
IMAGE                           ID             DISK USAGE   CONTENT SIZE   EXTRA
frappe/erpnext:v16              03c0b820346c       2.46GB          522MB    U   
grafana/grafana:10.3.3          8640e5038e83        548MB          113MB    U   
jaegertracing/all-in-one:1.54   f4044964505c        107MB         33.3MB    U   
livekit/livekit-server:latest   289262ffae8b        112MB         34.4MB    U   
llama-strix:latest              8f2ff76f057e       23.6GB          5.6GB        
mariadb:10.6                    ea23e7cd2533        440MB          108MB    U   
otel/opentelemetry-collector-contrib:0.96.0
                                7ef2a2ff46b9        309MB         65.1MB    U   
postgres:16                     f992505e18f1        641MB          166MB        
postgres:16-alpine              23e88eb049fd        395MB          111MB    U   
prom/prometheus:v2.50.0         042258e3578a        358MB          101MB    U   
qdrant/qdrant:latest            0425e3e03e7f        276MB         76.5MB    U   
redis:7-alpine                  ee64a64eaab6       61.2MB         17.7MB    U   
rocm/pytorch:latest             a3b658136210       42.4GB         10.9GB        
vllm/vllm-openai-rocm:v0.14.0   5b14bf147c66       39.8GB         9.06GB    U   
vllm/vllm-openai-rocm:v0.14.1   236900d57300       39.7GB         9.06GB    U   
yanwk/comfyui-boot:rocm7        2e646600f31c       52.3GB         14.2GB        
unergy@ryypol-16:~/BestBox$ 


---

unergy@ryypol-16:~/.cache$ cat ~/.bashrc
# ~/.bashrc: executed by bash(1) for non-login shells.
# see /usr/share/doc/bash/examples/startup-files (in the package bash-doc)
# for examples

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# don't put duplicate lines or lines starting with space in the history.
# See bash(1) for more options
HISTCONTROL=ignoreboth

# append to the history file, don't overwrite it
shopt -s histappend

# for setting history length see HISTSIZE and HISTFILESIZE in bash(1)
HISTSIZE=1000
HISTFILESIZE=2000

# check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# If set, the pattern "**" used in a pathname expansion context will
# match all files and zero or more directories and subdirectories.
#shopt -s globstar

# make less more friendly for non-text input files, see lesspipe(1)
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "${debian_chroot:-}" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set a fancy prompt (non-color, unless we know we "want" color)
case "$TERM" in
    xterm-color|*-256color) color_prompt=yes;;
esac

# uncomment for a colored prompt, if the terminal has the capability; turned
# off by default to not distract the user: the focus in a terminal window
# should be on the output of commands, not on the prompt
#force_color_prompt=yes

if [ -n "$force_color_prompt" ]; then
    if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
	# We have color support; assume it's compliant with Ecma-48
	# (ISO/IEC-6429). (Lack of such support is extremely rare, and such
	# a case would tend to support setf rather than setaf.)
	color_prompt=yes
    else
	color_prompt=
    fi
fi

if [ "$color_prompt" = yes ]; then
    PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
else
    PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '
fi
unset color_prompt force_color_prompt

# If this is an xterm set the title to user@host:dir
case "$TERM" in
xterm*|rxvt*)
    PS1="\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]$PS1"
    ;;
*)
    ;;
esac

# enable color support of ls and also add handy aliases
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    #alias dir='dir --color=auto'
    #alias vdir='vdir --color=auto'

    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# colored GCC warnings and errors
#export GCC_COLORS='error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01'

# some more ls aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# Add an "alert" alias for long running commands.  Use like so:
#   sleep 10; alert
alias alert='notify-send --urgency=low -i "$([ $? = 0 ] && echo terminal || echo error)" "$(history|tail -n1|sed -e '\''s/^\s*[0-9]\+\s*//;s/[;&|]\s*alert$//'\'')"'

# Alias definitions.
# You may want to put all your additions into a separate file like
# ~/.bash_aliases, instead of adding them here directly.
# See /usr/share/doc/bash-doc/examples in the bash-doc package.

if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# enable programmable completion features (you don't need to enable
# this, if it's already enabled in /etc/bash.bashrc and /etc/profile
# sources /etc/bash.bashrc).
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

# opencode
export PATH=/home/unergy/.opencode/bin:$PATH

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# HF token removed. Set HF_TOKEN in your environment; do NOT commit secrets.
export HF_TOKEN="${HF_TOKEN:-REDACTED}"
export PATH="$HOME/.local/bin:$PATH"

[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path bash)"
# Slack token removed. Set SLACK_BOT_TOKEN in your environment; do NOT commit secrets.
export SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:-REDACTED}"

# pnpm
export PNPM_HOME="/home/unergy/.local/share/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac
# pnpm end


# Telegram token removed. Set TELEGRAM_BOT_TOKEN in your environment; do NOT commit secrets.
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-REDACTED}"

