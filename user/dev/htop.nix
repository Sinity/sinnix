{
  config,
  lib,
  ...
}:
{
  programs.htop = {
    enable = true;
    settings =
      let
        fields = config.lib.htop.fields;
      in
      {
        fields = with fields; [
          PID
          USER
          PRIORITY
          NICE
          M_VIRT
          M_RESIDENT
          M_SHARE
          STATE
          PERCENT_CPU
          PERCENT_MEM
          TIME
          COMM
        ];
        hide_kernel_threads = true;
        hide_userland_threads = false;
        hide_running_in_container = false;
        shadow_other_users = false;
        show_thread_names = false;
        show_program_path = true;
        highlight_deleted_exe = true;
        highlight_megabytes = true;
        highlight_threads = true;
        highlight_changes = false;
        highlight_changes_delay_secs = 5;
        find_comm_in_cmdline = true;
        strip_exe_from_cmdline = true;
        show_merged_command = false;
        header_margin = 1;
        screen_tabs = true;
        detailed_cpu_time = false;
        cpu_count_from_one = false;
        show_cpu_usage = true;
        show_cpu_frequency = false;
        show_cpu_temperature = false;
        degree_fahrenheit = false;
        update_process_names = false;
        account_guest_in_cpu_meter = false;
        color_scheme = 0;
        enable_mouse = true;
        delay = 15;
        hide_function_bar = false;
        header_layout = "two_50_50";
        tree_view = false;
        sort_key = fields.PERCENT_CPU;
        tree_sort_key = fields.PID;
        sort_direction = -1;
        tree_sort_direction = 1;
        tree_view_always_by_pid = false;
        all_branches_collapsed = false;
        "screen:Main" =
          "PID USER PRIORITY NICE M_VIRT M_RESIDENT M_SHARE STATE PERCENT_CPU PERCENT_MEM TIME Command";
        "screen:Main.sort_key" = "PERCENT_CPU";
        "screen:Main.tree_sort_key" = "PID";
        "screen:Main.tree_view_always_by_pid" = "0";
        "screen:Main.tree_view" = "0";
        "screen:Main.sort_direction" = "-1";
        "screen:Main.tree_sort_direction" = "1";
        "screen:Main.all_branches_collapsed" = "0";
        "screen:I/O" =
          "PID USER IO_PRIORITY IO_RATE IO_READ_RATE IO_WRITE_RATE PERCENT_SWAP_DELAY PERCENT_IO_DELAY Command";
        "screen:I/O.sort_key" = "IO_RATE";
        "screen:I/O.tree_sort_key" = "PID";
        "screen:I/O.tree_view_always_by_pid" = "0";
        "screen:I/O.tree_view" = "0";
        "screen:I/O.sort_direction" = "-1";
        "screen:I/O.tree_sort_direction" = "1";
        "screen:I/O.all_branches_collapsed" = "0";
      }
      // (
        with config.lib.htop;
        leftMeters [
          (bar "LeftCPUs4")
          (bar "Memory")
          (bar "Swap")
        ]
      )
      // (
        with config.lib.htop;
        rightMeters [
          (bar "RightCPUs4")
          (text "Tasks")
          (text "LoadAverage")
          (text "Uptime")
        ]
      );
  };
}
