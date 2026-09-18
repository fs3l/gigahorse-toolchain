# Running Gigahorse in Docker

An alternative to the macOS setup in `README.md`. The container runs Linux, where
the build needs no patching at all — the macOS-specific steps (`-fopenmp`,
`libfunctors.dylib`, `install_name_tool`, `souffle-compile.py`) do not apply.

Requires Docker Desktop. Set **Settings → Resources → Memory** to **8 GB or more**
before starting, otherwise the Datalog compilation is killed by the OOM killer.

## 1. Start a container

On the host:

```
IMG=ghcr.io/nevillegrech/gigahorse-toolchain-deps-souffle24:latest
docker run --rm -it $IMG bash
```

This image is published by the upstream project and already contains Souffle
2.4.1, Boost, Z3 and mcpp. On Apple Silicon it runs under amd64 emulation and
prints a platform warning, which is harmless.

All remaining commands run **inside** the container.

## 2. Install uv

```
pip3 install uv
```

The published image predates the addition of uv to its Dockerfile, so it has to
be installed manually.

## 3. Install solc

```
B=https://github.com/ethereum/solidity/releases/download
V=v0.8.37
wget -O /usr/local/bin/solc $B/$V/solc-static-linux
chmod +x /usr/local/bin/solc
solc --version
```

## 4. Clone the repository

```
cd /
git clone --recursive https://github.com/fs3l/gigahorse-toolchain.git
cd gigahorse-toolchain
```

Use the HTTPS URL here, not the SSH one from `README.md` — the container has no
SSH key registered with GitHub.

## 5. Build the Souffle functor library

```
cd souffle-addon && make && cd ..
```

Plain `make`, with no adjustments. All tests pass on Linux, so there is no
`Error 201` to ignore.

## 6. Set up the Python environment

```
uv sync
```

## 7. Run

```
cd mytests && make
```

The first run compiles four Datalog programs to native binaries. That takes about
two minutes natively, but 15-20 minutes under amd64 emulation on Apple Silicon.
Later runs take seconds, because the binaries are cached in `../cache/`.

## Saving the compiled binaries

`docker run --rm` discards everything on exit, including the four compiled
binaries. To keep them, open a second terminal on the host while the container is
still running:

```
docker ps
docker commit <container-id> gigahorse-test
```

From then on:

```
docker run --rm -it gigahorse-test bash
cd /gigahorse-toolchain/mytests && make
```

That completes in seconds. To pick up later repository changes inside that image,
run `git pull` in it — the cache key is an MD5 of the Datalog source, which
changes to `mytests/` do not affect, so the cached binaries stay valid.

## Troubleshooting

`Killed signal terminated program cc1plus` — out of memory. The four Datalog
programs compile in parallel and need roughly 2-3 GB each. Raise Docker's memory
limit, or re-run the same command: programs that already compiled are cached, so
fewer compile in parallel on the second attempt.

`uv: command not found` — step 2 was skipped.

`solc: No such file or directory` — step 3 was skipped.

`docker: command not found` — you are inside the container. The `docker commit`
commands belong on the host.
