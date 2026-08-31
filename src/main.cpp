#ifndef XBOX
#error Must be built with nxdk
#endif

#include <SDL.h>
#include <SDL_image.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#include <hal/debug.h>
#pragma clang diagnostic pop
#include <hal/fileio.h>
#include <hal/video.h>
#include <nxdk/mount.h>
#include <pbkit/pbkit.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include <windows.h>
#pragma clang diagnostic pop

#include "debug_output.h"
#include "logger.h"
#include "result_store.h"
#include "runtime_config.h"
#include "test_driver.h"
#include "test_host.h"
#include "tests/busy_pfifo_tests.h"
#include "tests/cpu_floating_point_tests.h"
#include "tests/cpu_translation_block_tests.h"
#include "tests/fill_rate_tests.h"
#include "tests/game_load_composite_tests.h"
#include "tests/high_vertex_count_tests.h"
#include "tests/pfifo_array_element_tests.h"
#include "tests/pipeline_texture_switch_tests.h"
#include "tests/primitive_type_tests.h"
#include "tests/surface_rendering_tests.h"
#include "tests/tiny_draw_tests.h"
#include "tests/uniform_thrash_tests.h"
#include "tests/vertex_buffer_allocation_tests.h"

#include <fstream>

static constexpr const char* kLogFileName = "results.txt";

static const int kFramebufferWidth = 640;
static const int kFramebufferHeight = 480;
static const int kBitsPerPixel = 32;

static constexpr int kDelayOnFailureMilliseconds = 4000;

const UCHAR kSMCSlaveAddress = 0x20;
const UCHAR kSMCRegisterPower = 0x02;
const UCHAR kSMCPowerShutdown = 0x80;

static bool EnsureDriveMounted(char drive_letter);
static bool LoadConfig(RuntimeConfig& config, std::vector<std::string>& errors);
static bool RunTests(RuntimeConfig& config, TestHost& host, std::vector<std::shared_ptr<TestSuite>>& test_suites);
static void RegisterSuites(TestHost& host, RuntimeConfig& config, std::vector<std::shared_ptr<TestSuite>>& test_suites,
                           const std::string& output_directory);
static void Shutdown();

extern "C" __cdecl int automount_d_drive(void);

int main() {
  automount_d_drive();
  debugPrint("Set video mode\n");
  if (!XVideoSetMode(kFramebufferWidth, kFramebufferHeight, kBitsPerPixel, REFRESH_DEFAULT)) {
    debugPrint("Failed to set video mode\n");
    Sleep(kDelayOnFailureMilliseconds);
    return 1;
  }

  int status = pb_init();
  if (status) {
    debugPrint("pb_init Error %d\n", status);
    Sleep(kDelayOnFailureMilliseconds);
    return 1;
  }

  debugPrint("Initializing...\n");
  pb_show_debug_screen();

  if (SDL_Init(SDL_INIT_GAMECONTROLLER)) {
    debugPrint("Failed to initialize SDL_GAMECONTROLLER.\n");
    debugPrint("%s\n", SDL_GetError());
    pb_show_debug_screen();
    Sleep(kDelayOnFailureMilliseconds);
    return 1;
  }

  if (!(IMG_Init(IMG_INIT_PNG) & IMG_INIT_PNG)) {
    debugPrint("Failed to initialize SDL_image PNG mode.\n");
    pb_show_debug_screen();
    Sleep(kDelayOnFailureMilliseconds);
    pb_kill();
    return 1;
  }

  RuntimeConfig config;
  {
    std::vector<std::string> errors;
    if (!LoadConfig(config, errors)) {
      debugPrint("Failed to load config, using default values.\n");
      for (auto& err : errors) {
        debugPrint("%s\n", err.c_str());
      }
      pb_show_debug_screen();
    }
  }

  if (!EnsureDriveMounted(config.output_directory_path().front())) {
    debugPrint("Failed to mount %s, please make sure output directory is on a writable drive.\n",
               config.output_directory_path().c_str());
    pb_show_debug_screen();
    Sleep(kDelayOnFailureMilliseconds);
    pb_kill();
    return 1;
  };

  TestHost::EnsureFolderExists(config.output_directory_path());

  std::vector<std::shared_ptr<TestSuite>> test_suites;
  TestHost host(kFramebufferWidth, kFramebufferHeight);
  host.SetWarmupIterations(config.warmup_iterations());
  host.SetMeasurementIterationsMultiplier(config.measurement_iterations_multiplier());
  host.SetGpuCompletionMode(config.gpu_completion_mode());
  RegisterSuites(host, config, test_suites, config.output_directory_path());

  {
    std::vector<std::string> errors;
    if (!config.ApplyConfig(test_suites, errors)) {
      debugClearScreen();
      debugPrint("Failed to apply runtime config:\n");
      for (auto& err : errors) {
        debugPrint("%s\n", err.c_str());
      }
      Sleep(kDelayOnFailureMilliseconds);
      pb_kill();
      return 1;
    }
  }

  pb_show_front_screen();
  debugClearScreen();
  if (!RunTests(config, host, test_suites)) {
    pb_kill();
    return 2;
  }

  pb_kill();
  return 0;
}

static bool EnsureDriveMounted(char drive_letter) {
  if (nxIsDriveMounted(drive_letter)) {
    return true;
  }

  char dos_path[4] = "x:\\";
  dos_path[0] = drive_letter;
  char device_path[256] = {0};
  if (XConvertDOSFilenameToXBOX(dos_path, device_path) != STATUS_SUCCESS) {
    return false;
  }

  if (!strstr(device_path, R"(\Device\Harddisk0\Partition)")) {
    return false;
  }
  device_path[28] = 0;

  return nxMountDrive(drive_letter, device_path);
}

static bool LoadConfig(RuntimeConfig& config, std::vector<std::string>& errors) {
#ifdef RUNTIME_CONFIG_PATH
  if (!EnsureDriveMounted(RUNTIME_CONFIG_PATH[0])) {
    debugPrint("Ignoring missing config at %s\n", RUNTIME_CONFIG_PATH);
  } else {
    if (config.LoadConfig(RUNTIME_CONFIG_PATH, errors)) {
      return true;
    } else {
      debugPrint("Failed to load config at %s\n", RUNTIME_CONFIG_PATH);
    }
  }
#endif

  return config.LoadConfig("d:\\xemu_perf_tests_config.json", errors);
}

static void Shutdown() {
  // TODO: HalInitiateShutdown doesn't seem to cause Xemu to actually close.
  // This never sends the SMC command indicating that a shutdown should occur (at least, it never makes it to
  // `smc_write_data` to be processed).
  // HalInitiateShutdown();

  HalWriteSMBusValue(kSMCSlaveAddress, kSMCRegisterPower, FALSE, kSMCPowerShutdown);
  while (true) {
    Sleep(30000);
  }
}

static bool RunTests(RuntimeConfig& config, TestHost& host, std::vector<std::shared_ptr<TestSuite>>& test_suites) {
  std::string log_file = config.output_directory_path() + "\\" + kLogFileName;
  std::string archive_error;
  if (!ArchiveCurrentResults(config.output_directory_path(), archive_error)) {
    debugClearScreen();
    debugPrint("Cannot preserve previous result.\n%s\n\nCurrent file remains at:\n%s\n",
               archive_error.c_str(), log_file.c_str());
    pb_show_debug_screen();
    Sleep(kDelayOnFailureMilliseconds);
    return false;
  }
  Logger::Initialize(log_file, true);
  host.ResetResultLogState();
  if (config.has_resolved_plan()) {
    host.ConfigureResolvedPlan(config.plan_id(), config.selected_test_ids());
  }

  TestDriver driver(host, test_suites, kFramebufferWidth, kFramebufferHeight, false, config.disable_autorun(),
                    config.enable_autorun_immediately(),
                    config.output_directory_path());

  Logger::Log() << "[" << std::endl;
  driver.Run();
  Logger::Log() << "]" << std::endl;
  PrintMsg("Test loop completed normally\n");
  Logger::Log().close();

  std::string plan_error;
  const bool plan_complete = host.ValidateResolvedPlan(plan_error);
  if (config.has_resolved_plan()) {
    const std::string plan_result_path =
        config.output_directory_path() + "\\resolved-plan-result.json";
    std::ofstream plan_result(plan_result_path, std::ios_base::trunc);
    if (!plan_result) {
      debugPrint("Failed to write resolved plan result at %s\n", plan_result_path.c_str());
      return false;
    }
    plan_result << "{\n  \"schema_version\": 1,\n  \"plan_id\": \""
                << config.plan_id() << "\",\n  \"selected_leaf_count\": "
                << config.selected_leaf_count() << ",\n  \"emitted_leaf_count\": "
                << host.EmittedLeafCount() << ",\n  \"completion\": \""
                << (plan_complete ? "COMPLETE" : "INCOMPLETE") << "\"\n}\n";
    plan_result.close();
    if (!plan_result) {
      debugPrint("Failed to finalize resolved plan result at %s\n", plan_result_path.c_str());
      return false;
    }
  }

  const bool oracle_pass = host.OracleFailureCount() == 0;
  const bool soft_pass = host.SoftFailureCount() == 0;
  const bool run_pass = plan_complete && oracle_pass && soft_pass;
  debugClearScreen();
  debugPrint("xemu perf tests: %s\n\n", run_pass ? "PASS" : "FAIL");
  debugPrint("Catalog: %s\n", TestCatalogId());
  debugPrint("Results: %s\n", log_file.c_str());
  debugPrint("Leaves: %lu  Groups: %lu\n", host.RecordedLeafCount(),
             host.RecordedGroupCount());
  debugPrint("Oracle failures: %lu\n", host.OracleFailureCount());
  debugPrint("Soft failures: %lu\n", host.SoftFailureCount());
  if (!soft_pass) {
    debugPrint("First failure: %s\n", host.FirstSoftFailure().c_str());
  } else if (!oracle_pass) {
    debugPrint("First failure: %s\n", host.FirstOracleFailure().c_str());
  }
  if (!plan_complete) {
    debugPrint("Plan: INCOMPLETE\n%s\n", plan_error.c_str());
  } else {
    debugPrint("Plan: COMPLETE\n");
  }
  debugPrint("\nFinal screen: %lu seconds\n",
             config.reboot_or_shutdown_delay_ms() / 1000);
  pb_show_debug_screen();
  // This configurable hold is zero for unattended runners and should be at
  // least 30 seconds in physical-console plans. No hidden UI delay is added.
  Sleep(config.reboot_or_shutdown_delay_ms());

  if (config.enable_shutdown_on_completion()) {
    Shutdown();
  }
  return run_pass;
}

static void RegisterSuites(TestHost& host, RuntimeConfig& runtime_config,
                           std::vector<std::shared_ptr<TestSuite>>& test_suites, const std::string& output_directory) {
  const auto& config = runtime_config.test_suite_config();

#define REG_TEST(CLASS_NAME)                                                   \
  {                                                                            \
    auto suite = std::make_shared<CLASS_NAME>(host, output_directory, config); \
    test_suites.push_back(suite);                                              \
  }

  // -- Begin REG_TEST --
  REG_TEST(BusyPfifoTests)
  REG_TEST(CpuFloatingPointTests)
  REG_TEST(CpuTranslationBlockTests)
  REG_TEST(FillRateTests)
  REG_TEST(GameLoadCompositeTests)
  REG_TEST(HighVertexCountTests)
  REG_TEST(PfifoArrayElementTests)
  REG_TEST(PipelineTextureSwitchTests)
  REG_TEST(PrimitiveTypeTests)
  REG_TEST(SurfaceRenderingTests)
  REG_TEST(TinyDrawTests)
  REG_TEST(UniformThrashTests)
  REG_TEST(VertexBufferAllocationTests)
  // -- End REG_TEST --

#undef REG_TEST
}
