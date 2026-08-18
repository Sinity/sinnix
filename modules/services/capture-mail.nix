# capture-mail: mbsync IMAP -> Maildir mirror into the capture lake
# (sinnix-9dml).
#
# Native-format doctrine (per the bead's 2026-08-12 rigor-pass note and the
# aw-rollup lesson on sinnix-olm2's close): a Maildir is already the durable
# store IMAP clients understand, so this lane does NOT go through the
# sinnix-capture envelope writer -- mbsync writes the Maildir directly under
# commsRoot/mail, and that directory tree IS the capture.
#
# `Expunge None` in the generated mbsync config is deliberate, not an
# oversight: this lane exists to survive server-side and client-side
# deletes, so a message that disappears upstream (spam-folder purge, "empty
# trash", account migration) stays mirrored here rather than being dropped
# on the next sync -- the no-retention capture doctrine applied to mail.
#
# Default-off (`sinnix.services.capture-mail.enable`) with a NAMED secret
# slot: modules/secrets.nix declares `mail-app-password` as a runtime secret
# contract, so config.sinnix.secrets.paths.mail-app-password resolves and
# this module evaluates cleanly whether or not the ciphertext exists yet.
# The credential is shared with capture-calendar.nix (same account, one
# app-specific password).
#
# Operator steps to go live:
#   1. Create an app-specific password for the target mail account (Gmail:
#      https://myaccount.google.com/apppasswords -- requires 2FA already
#      enabled; any other IMAP provider's equivalent works too, just point
#      imapHost/imapUser at it).
#   2. echo -n '<app-password>' | agenix -e secret/mail-app-password.age
#      (run from `nix develop`).
#   3. sinnix.services.capture-mail = { enable = true; imapUser =
#      "you@example.com"; }; on the target host (imapHost/patterns default
#      to Gmail's INBOX + All Mail; override for another provider).
#   4. switch.
{
  mkServiceModule,
  mkCaptureLane,
  pkgs,
  lib,
  config,
  ...
}@args:
let
  username = config.sinnix.user.name;
  maildirDir = "${config.sinnix.paths.commsRoot}/mail";
  secretPaths = config.sinnix.secrets.paths;
  cfg = config.sinnix.services.capture-mail;

  mbsyncrc = pkgs.writeText "sinnix-capture-mail.mbsyncrc" ''
    IMAPAccount capture-mail
    Host ${cfg.imapHost}
    User ${cfg.imapUser}
    PassCmd "cat ${secretPaths.mail-app-password}"
    TLSType IMAPS
    CertificateFile ${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt

    IMAPStore capture-mail-remote
    Account capture-mail

    MaildirStore capture-mail-local
    Subfolders Verbatim
    Path ${maildirDir}/
    Inbox ${maildirDir}/INBOX

    Channel capture-mail
    Far :capture-mail-remote:
    Near :capture-mail-local:
    Patterns ${lib.concatMapStringsSep " " (p: "\"${p}\"") cfg.patterns}
    Create Near
    Expunge None
    SyncState *
  '';

  syncer = pkgs.writeShellApplication {
    name = "capture-mail-sync";
    runtimeInputs = [
      pkgs.isync
      pkgs.coreutils
    ];
    text = ''
      set -euo pipefail

      config_file="$1"
      maildir="$2"

      mbsync -c "$config_file" capture-mail

      # mbsync's own sync-state bookkeeping may or may not touch a visible
      # mtime on a fully-quiescent mailbox; a marker independent of that
      # internal detail is what the captures[] staleness check actually
      # needs -- "did this unit complete a pass," not "did new mail arrive."
      date -u -Iseconds > "$maildir/.sinnix-last-sync"
    '';
  };
in
mkServiceModule (mkCaptureLane {
  name = "capture-mail";
  description = "mbsync IMAP -> Maildir mirror";
  inherit username;
  laneDir = maildirDir;
  mode = "poll";
  captureName = "mail";
  cadenceSeconds = cfg.intervalSec;
  staleAfterSeconds = 7200;
  execStart = "${syncer}/bin/capture-mail-sync ${mbsyncrc} ${maildirDir}";
  environment = [ "TMPDIR=/tmp" ];
  privateTmp = true;
  timer = {
    intervalSec = cfg.intervalSec;
    onBootSec = "3min";
    accuracySec = "1min";
  };
  unitDescription = "mbsync IMAP -> Maildir sync pass";
  timerDescription = "Periodic trigger for the mail capture mirror";
  extraOptions = {
    imapHost = lib.mkOption {
      type = lib.types.str;
      default = "imap.gmail.com";
      description = "IMAPS host to sync from.";
    };
    imapUser = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "IMAP username (full email address for Gmail). Must be set before enabling.";
    };
    patterns = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        "INBOX"
        "[Gmail]/All Mail"
      ];
      description = ''
        mbsync Channel Patterns -- which remote folders to mirror. The
        default is the bead's accepted first increment (INBOX + Gmail's
        unified archive, which already contains every non-trashed/non-spam
        message including labels applied via IMAP); widen this list (or
        switch to lieer for full label fidelity) only once that's actually
        wanted.
      '';
    };
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 900;
      description = "Seconds between sync passes.";
    };
  };
  extraConfig = _: {
    assertions = [
      {
        assertion = cfg.imapUser != null;
        message = "sinnix.services.capture-mail.enable requires sinnix.services.capture-mail.imapUser to be set.";
      }
    ];
  };
}) args
