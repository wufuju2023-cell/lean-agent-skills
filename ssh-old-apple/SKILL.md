---
name: ssh-old-apple
description: SSH into the old Apple/Windows machine (Tailscale host <host>, user 12345) for remote commands, file transfer, or troubleshooting. Use when the user asks to run something on the old Windows machine / <host> / desktop-qfu0fcf, or to transfer files to/from it.
---

# SSH to the old Apple/Windows machine

## Connection facts

| Item | Value |
|---|---|
| SSH alias | `<host>` (defined in `~/.ssh/config`) |
| Tailscale IP | `<host-ip>` |
| Remote user | `12345` (Windows, member of Administrators) |
| Local user | `a` |
| Local key | `~/.ssh/id_ed25519_windows` |
| Auth | Key-based; `BatchMode=yes` works |
| Remote default shell | PowerShell |
| OS | Windows 10 (Boot Camp), hostname `DESKTOP-QFU0FCF` |

## Basic commands

```bash
ssh <host> 'whoami'
ssh <host> 'cmd /c "dir C:\ /a"'
ssh <host> 'powershell -NoProfile -Command "Get-Process | Select -First 5"'
```

The remote default shell is PowerShell. Use `cmd /c` when you need cmd.exe
syntax, and `powershell -NoProfile -Command` for PowerShell.

To avoid quoting pain, encode a PowerShell script as UTF-16LE base64 and use
`-EncodedCommand`:

```bash
iconv -f UTF-8 -t UTF-16LE script.ps1 | base64 -w0 > /tmp/opencode/enc.txt
ssh <host> "powershell -NoProfile -EncodedCommand \$(cat /tmp/opencode/enc.txt)"
```

## File transfer

Test `scp`/`sftp` before relying on them. They have failed against this host
with `Received message too long` because shell/profile noise corrupts the
protocol.

Safe fallback: base64 with markers.

```bash
# Put this in fetch.ps1:
#   Write-Output "BEGIN_B64"
#   Write-Output ([Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\path\file")))
#   Write-Output "END_B64"
iconv -f UTF-8 -t UTF-16LE fetch.ps1 | base64 -w0 > /tmp/opencode/enc.txt
ssh <host> "powershell -NoProfile -EncodedCommand \$(cat /tmp/opencode/enc.txt)" 2>/dev/null \
  | sed -n '/BEGIN_B64/,/END_B64/p' \
  | grep -v 'BEGIN_B64\|END_B64' \
  | tr -d '\n' | base64 -d > out.file
```

## Known gotchas

1. **Output pollution.** The remote PowerShell profile can print OSC terminal
   escapes and profile noise. Filter output:
   ```bash
   ssh <host> ... 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g'
   ```
2. **Admin authorized_keys.** For Administrators, sshd reads
   `C:\ProgramData\ssh\administrators_authorized_keys`, not
   `%USERPROFILE%\.ssh\authorized_keys`.
3. **`ssh-copy-id` does not work.** The remote default shell is PowerShell, so
   use the `-EncodedCommand` pattern instead.
4. **Quoting.** Quoting through bash -> ssh -> PowerShell is fragile. Prefer
   `-EncodedCommand` for anything nontrivial.
5. **The F: USB disk has moved.** It is now attached to the new Linux machine;
   do not expect it on the old Windows host.

## Reverse access

Verify before relying on it: the old Windows machine can reach this machine
over Tailscale as `<user>@<host>` (port 22). The old `<user>@<host>`
WSL address is obsolete.

## Secrets

Key authentication is already configured, so no password prompt is normally
needed. If key auth breaks, use the masked-prompt helper (Zenity on a desktop,
no-echo TTY prompt over SSH):

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force ssh <host> ...
```
