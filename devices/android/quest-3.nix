{
  device = {
    name = "quest-3";
    abi = "arm64-v8a";
    user = 0;
  };

  # System software remains Quest-owned.  This profile only preserves the
  # directly observed, USB-development settings; package drift is reported,
  # never removed.
  apps = {
    # Side-loaded or store apps observed on this headset.  They remain
    # headset-managed: this profile documents their expected presence without
    # claiming an install source or removing any of them.
    attended = [
      "chat.fluffy.fluffychat"
      "com.aurora.store"
      "com.apk.editor"
      "com.beatgames.beatsaber"
      "com.CarbonStudio.TheWizards"
      "com.crytek.climb2"
      "com.deovr.gearvr"
      "com.DigitalLode.Espire2"
      "com.EpicScapes.RealmsOfFlow"
      "com.FunktronicLabs.TheLightBrigade"
      "com.JorgeJGnz.PhysHand"
      "com.LiminalVR.Liminal"
      "com.MightyYellStudios.WobblyKnightMaster"
      "com.OmnifariousStudiosLLC.ProjectDemigod"
      "com.SchellGames.DieScreaming"
      "com.SchellGames.LostRecipes"
      "com.Trebuchet.PrisonBossVR"
      "com.VirZOOM.FLY"
      "com.google.android.apps.youtube.vr.oculus"
      "com.holonautic.cybrix"
      "com.meta.curio.ruler"
      "com.meta.handseducationmodule"
      "com.meta.shell.env.footprint.haven2025"
      "com.meta.shell.env.vista.calming"
      "com.oculus.accountscenter"
      "com.oculus.fitnesstracker"
      "com.oculus.paracosmaavalanche"
      "com.oculus.vrprivacycheckup"
      "com.onemt.and.kc"
      "com.puddle.thrasher_release"
      "com.qcxr.qcxr"
      "com.rarlab.rar"
      "com.resolutiongames.homesports"
      "com.resolutiongames.trolin"
      "com.streamlabs"
      "com.threethan.launcher"
      "com.threethan.launcher.metastore"
      "com.truantpixel.Runner"
      "com.valvesoftware.steamlinkvr"
      "com.voidroom.TeaForGod"
      "com.voidroom.TeaForGodEmperor"
      "com.vrchat.oculus.quest"
      "com.zerotier.one"
      "com.ZeroTransform.VStreamer_Live"
      "geniesoft.io.DancingArrow"
      "github.paroj.dsub2000"
      "org.fdroid.fdroid"
      "org.godotengine.open_saber_plus"
      "pupper.dev.barkvr"
      "quest.side.vr"
      "quest.eleven.forfunlabs"
      "studio.NewFolderGames.TitansClinic"
    ];
    cleanup = "report";
  };

  android.settings = {
    global = {
      # Keep an attached development headset awake while USB-powered.
      stay_on_while_plugged_in = 2;
      animator_duration_scale = "0.5";
      transition_animation_scale = "0.5";
      window_animation_scale = "0.5";
    };
    system.screen_off_timeout = 86400000;
  };
}
