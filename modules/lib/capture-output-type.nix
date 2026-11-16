# Shared output contract for unit-owned and externally produced captures.
{ lib }:
lib.types.submodule {
  options = {
    name = lib.mkOption { type = lib.types.str; };
    path = lib.mkOption { type = lib.types.str; };
    producerProgressPath = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = ''
        Optional producer-owned marker updated only after real output is
        committed. The health sweep can stat this one path when its bounded
        file scan cannot determine freshness.
      '';
    };
    cadenceSeconds = lib.mkOption {
      type = lib.types.nullOr lib.types.int;
      default = null;
    };
    eventDriven = lib.mkOption {
      type = lib.types.bool;
      default = false;
    };
    staleAfterSeconds = lib.mkOption {
      type = lib.types.nullOr lib.types.int;
      default = null;
      description = ''
        Absolute staleness budget in seconds, independent of
        cadenceSeconds. Event-driven lanes (eventDriven = true)
        have no numeric cadence for the health sweep's 2*cadence
        staleness check, so this is the only signal that flags
        them stale when writes stop. Lanes with a numeric
        cadenceSeconds may set this too; the health sweep flags a
        lane stale when EITHER threshold is exceeded.
      '';
    };
    livenessProbe = lib.mkOption {
      type = lib.types.nullOr (
        lib.types.submodule {
          options = {
            command = lib.mkOption {
              type = lib.types.str;
              description = ''
                Shell snippet run as `bash -c` under timeout to check whether the upstream
                source is present and publishing, independently of unit status.
                Exit 0 for present, 1 for confirmed absent, or any other code
                (including timeout 124) when the answer is unknown.
              '';
            };
            timeoutSeconds = lib.mkOption {
              type = lib.types.ints.positive;
              default = 5;
              description = ''
                Bound on the probe's runtime. The health sweep runs
                on a 1-minute cadence against every capture
                lane, so a hung probe must not hang the sweep;
                a timeout is reported as unknown, never healthy.
              '';
            };
          };
        }
      );
      default = null;
      description = ''
        Optional upstream-liveness probe. Most lanes have no
        cheap probe available -- leave this null and the lane
        behaves exactly as it did before this option existed.
        staleAfterSeconds alone can only detect "no writes
        recently"; it structurally cannot distinguish a
        legitimately quiet lane from one whose upstream
        publisher never registered in the first place, so
        lanes where that distinction is cheaply checkable
        should declare a probe here instead of relying solely
        on a longer budget.
      '';
    };
    requiredPayloadFields = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [
        "window_class"
        "geometry.width"
      ];
      description = ''
        Dotted paths into a sinnix-capture-v1 record's payload. The health
        sweep flags a capture when a declared field is null or empty in every
        sampled record. Declare only fields a healthy record always carries;
        leave this empty for captures that are not JSONL records.
      '';
    };
  };
}
