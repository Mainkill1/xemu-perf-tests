#include "runtime_config.h"

#include <fstream>
#include <list>

#include "tiny-json.h"
#include "test_catalog.h"

#define MAX_CONFIG_FILE_SIZE (1024 * 1024)

static bool ParseTestSuites(
    json_t const* test_suites, std::vector<std::string>& errors,
    std::map<std::string, RuntimeConfig::SkipConfiguration>& skipped_test_suites,
    std::map<std::string, std::map<std::string, RuntimeConfig::SkipConfiguration>>& skipped_test_cases);

//! C++ wrapper around Tiny-JSON jsonPool_t
class JSONParser : jsonPool_t {
 public:
  JSONParser() : jsonPool_t{&Alloc, &Alloc} {}
  explicit JSONParser(const char* str) : jsonPool_t{&Alloc, &Alloc}, json_string_{str} {
    root_node_ = json_createWithPool(json_string_.data(), this);
  }

  JSONParser(const JSONParser&) = delete;
  JSONParser(JSONParser&&) = delete;
  JSONParser& operator=(const JSONParser&) = delete;
  JSONParser& operator=(JSONParser&&) = delete;

  [[nodiscard]] json_t const* root() const { return root_node_; }

 private:
  static json_t* Alloc(jsonPool_t* pool) {
    const auto list_pool = static_cast<JSONParser*>(pool);
    list_pool->object_list_.emplace_back();
    return &list_pool->object_list_.back();
  }

  std::list<json_t> object_list_{};
  std::string json_string_{};
  json_t const* root_node_{};
};

bool RuntimeConfig::LoadConfig(const char* config_file_path, std::vector<std::string>& errors) {
  std::string dos_style_path = config_file_path;
  std::replace(dos_style_path.begin(), dos_style_path.end(), '/', '\\');

  std::string json_string;

  {
    std::ifstream config_file(dos_style_path.c_str());
    if (!config_file) {
      errors.push_back(std::string("Missing config file at ") + config_file_path);
      return false;
    }

    config_file.seekg(0, std::ios::end);
    auto end_pos = config_file.tellg();
    config_file.seekg(0, std::ios::beg);
    std::streamsize file_size = end_pos - config_file.tellg();

    if (file_size > MAX_CONFIG_FILE_SIZE || file_size == -1) {
      errors.push_back(std::string("Config file at ") + config_file_path + " is too large.");
      return false;
    }

    json_string.resize(file_size);
    config_file.read(&json_string[0], file_size);
  }

  return LoadConfigBuffer(json_string, errors);
}

static bool LoadBool(json_t const* object, const char* key, bool& out) {
  auto property = json_getProperty(object, key);
  if (!property) {
    return true;
  }

  if (json_getType(property) != JSON_BOOLEAN) {
    return false;
  }

  out = json_getBoolean(property);
  return true;
};

static bool LoadString(json_t const* object, const char* key, std::string& out) {
  auto property = json_getProperty(object, key);
  if (!property) {
    return true;
  }

  if (json_getType(property) != JSON_TEXT) {
    return false;
  }

  out = json_getValue(property);
  return true;
};

static bool LoadUint32(json_t const* object, const char* key, uint32_t& out) {
  auto property = json_getProperty(object, key);
  if (!property) {
    return true;
  }

  if (json_getType(property) != JSON_INTEGER) {
    return false;
  }

  auto value = json_getInteger(property);
  if (value < 0) {
    return false;
  }

  out = static_cast<uint32_t>(value & 0xFFFFFFFF);
  return true;
};

static bool IsSha256Id(const std::string &value) {
  if (value.size() != 71 || value.compare(0, 7, "sha256:") != 0) {
    return false;
  }
  for (size_t i = 7; i < value.size(); ++i) {
    const char c = value[i];
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) {
      return false;
    }
  }
  return true;
}

static int GameLoadCompositeStageIndex(const std::string &name) {
  if (name == "cpu") return 0;
  if (name == "pfifo") return 1;
  if (name == "alpha_overdraw") return 2;
  if (name == "streaming_surface_reuse") return 3;
  if (name == "combined") return 4;
  if (name == "full_system") return 5;
  return -1;
}

static int GameLoadCompositeCrossTitleStageIndex(const std::string &name) {
  if (name == "queued_vertex_cpu_writes") return 0;
  if (name == "pgr2_small_draws") return 1;
  if (name == "texture_update_reuse") return 2;
  if (name == "surface_reuse") return 3;
  if (name == "pipeline_state_churn") return 4;
  if (name == "blend_constant_reuse") return 5;
  if (name == "texture_binding_reuse") return 6;
  if (name == "pgr2_lagspot_inline_elements") return 7;
  if (name == "scaled_surface_pressure") return 8;
  if (name == "s3tc_streaming_fenced_draws" ||
      name == "s3tc_streaming_burst") return 9;
  if (name == "gpu_wait_control") return 10;
  return -1;
}

static int GameLoadCompositeS3tcSyncFactorStageIndex(const std::string &name) {
  if (name == "dxt1_same_address_wait") return 0;
  if (name == "dxt1_same_address_queued") return 1;
  if (name == "dxt1_ring") return 2;
  if (name == "dxt1_dirty_once") return 3;
  if (name == "rgba8_same_address_wait") return 4;
  if (name == "rgba8_same_address_queued") return 5;
  if (name == "rgba8_ring") return 6;
  if (name == "rgba8_dirty_once") return 7;
  if (name == "bc2_native_eligible") return 8;
  if (name == "bc2_bordered_fallback") return 9;
  if (name == "bc3_native_eligible") return 10;
  if (name == "bc3_bordered_fallback") return 11;
  return -1;
}

static bool ParseGameLoadCompositeStageValues(
    json_t const *object, const char *name,
    std::array<uint32_t, TestSuite::Config::kGameLoadCompositeStageCount> &values,
    bool allow_zero, std::vector<std::string> &errors) {
  auto stage_values = json_getProperty(object, name);
  if (!stage_values) {
    return true;
  }
  if (json_getType(stage_values) != JSON_OBJ) {
    errors.emplace_back(std::string("game_load_composite.long_unlocked_scene[") + name +
                        "] must be an object");
    return false;
  }
  for (auto stage = json_getChild(stage_values); stage; stage = json_getSibling(stage)) {
    const int index = GameLoadCompositeStageIndex(json_getName(stage));
    if (index < 0 || json_getType(stage) != JSON_INTEGER) {
      errors.emplace_back(std::string("game_load_composite.long_unlocked_scene[") + name +
                          "] contains an invalid stage/value");
      return false;
    }
    const auto value = json_getInteger(stage);
    if (value < 0 || value > 100000 || (!allow_zero && value == 0)) {
      errors.emplace_back(std::string("game_load_composite.long_unlocked_scene[") + name +
                          "] values must be integers from " + (allow_zero ? "0" : "1") + " through 100000");
      return false;
    }
    values[index] = static_cast<uint32_t>(value);
  }
  return true;
}

static bool ParseGameLoadCompositeConfig(json_t const *root, TestSuite::Config &config,
                                         std::vector<std::string> &errors) {
  auto game_load_composite = json_getProperty(root, "game_load_composite");
  if (!game_load_composite) {
    return true;
  }
  if (json_getType(game_load_composite) != JSON_OBJ) {
    errors.emplace_back("game_load_composite must be an object");
    return false;
  }
  auto long_scene = json_getProperty(game_load_composite, "long_unlocked_scene");
  if (long_scene) {
    if (json_getType(long_scene) != JSON_OBJ) {
      errors.emplace_back("game_load_composite[long_unlocked_scene] must be an object");
      return false;
    }

    if (!LoadUint32(long_scene, "stage_mask", config.game_load_composite_stage_mask) ||
        !config.game_load_composite_stage_mask ||
        (config.game_load_composite_stage_mask &
         ~TestSuite::Config::kAllGameLoadCompositeStages)) {
      errors.emplace_back(
          "game_load_composite.long_unlocked_scene[stage_mask] must select bits 0 through 5");
      return false;
    }

    auto stages = json_getProperty(long_scene, "stages");
    if (stages) {
      if (json_getType(stages) != JSON_OBJ) {
        errors.emplace_back(
            "game_load_composite.long_unlocked_scene[stages] must be an object");
        return false;
      }
      uint32_t stage_list_mask = 0;
      for (auto stage = json_getChild(stages); stage; stage = json_getSibling(stage)) {
        const int index = GameLoadCompositeStageIndex(json_getName(stage));
        if (index < 0 || json_getType(stage) != JSON_BOOLEAN) {
          errors.emplace_back(
              "game_load_composite.long_unlocked_scene[stages] contains an invalid stage/value");
          return false;
        }
        if (json_getBoolean(stage)) {
          stage_list_mask |= 1U << index;
        }
      }
      config.game_load_composite_stage_mask &= stage_list_mask;
      if (!config.game_load_composite_stage_mask) {
        errors.emplace_back("game_load_composite.long_unlocked_scene selects no stages");
        return false;
      }
    }

    if (!ParseGameLoadCompositeStageValues(long_scene, "measurement_iterations_multiplier",
                                           config.game_load_composite_stage_multipliers,
                                           false, errors) ||
        !ParseGameLoadCompositeStageValues(long_scene, "warmup_iterations",
                                           config.game_load_composite_stage_warmups,
                                           true, errors)) {
      return false;
    }

    auto gpu_precondition = json_getProperty(long_scene, "gpu_precondition");
    if (gpu_precondition) {
      if (json_getType(gpu_precondition) != JSON_OBJ ||
          !LoadUint32(gpu_precondition, "alpha_draws",
                      config.game_load_composite_gpu_precondition_alpha_draws) ||
          config.game_load_composite_gpu_precondition_alpha_draws > 1000000) {
        errors.emplace_back(
            "game_load_composite.long_unlocked_scene[gpu_precondition.alpha_draws] must be 0 through 1000000");
        return false;
      }
    }
  }

  auto cross_title = json_getProperty(game_load_composite, "cross_title_hotpath");
  if (cross_title) {
    if (json_getType(cross_title) != JSON_OBJ) {
      errors.emplace_back("game_load_composite[cross_title_hotpath] must be an object");
      return false;
    }

    if (!LoadBool(cross_title, "fast_smoke",
                  config.game_load_composite_cross_title_fast_smoke)) {
      errors.emplace_back("game_load_composite.cross_title_hotpath[fast_smoke] must be boolean");
      return false;
    }

    if (!LoadUint32(cross_title, "stage_mask",
                    config.game_load_composite_cross_title_stage_mask) ||
        !config.game_load_composite_cross_title_stage_mask ||
        (config.game_load_composite_cross_title_stage_mask &
         ~TestSuite::Config::kAllGameLoadCompositeCrossTitleStages)) {
      errors.emplace_back(
          "game_load_composite.cross_title_hotpath[stage_mask] must select bits 0 through 10");
      return false;
    }

    auto stages = json_getProperty(cross_title, "stages");
    if (stages) {
      if (json_getType(stages) != JSON_OBJ) {
        errors.emplace_back(
            "game_load_composite.cross_title_hotpath[stages] must be an object");
        return false;
      }
      uint32_t stage_list_mask = 0;
      for (auto stage = json_getChild(stages); stage; stage = json_getSibling(stage)) {
        const int index = GameLoadCompositeCrossTitleStageIndex(json_getName(stage));
        if (index < 0 || json_getType(stage) != JSON_BOOLEAN) {
          errors.emplace_back(
              "game_load_composite.cross_title_hotpath[stages] contains an invalid stage/value");
          return false;
        }
        if (json_getBoolean(stage)) {
          stage_list_mask |= 1U << index;
        }
      }
      config.game_load_composite_cross_title_stage_mask &= stage_list_mask;
      if (!config.game_load_composite_cross_title_stage_mask) {
        errors.emplace_back("game_load_composite.cross_title_hotpath selects no stages");
        return false;
      }
    }
  }

  auto sync_factor = json_getProperty(game_load_composite, "s3tc_sync_factor");
  if (sync_factor) {
    if (json_getType(sync_factor) != JSON_OBJ) {
      errors.emplace_back("game_load_composite[s3tc_sync_factor] must be an object");
      return false;
    }

    if (!LoadUint32(sync_factor, "stage_mask",
                    config.game_load_composite_s3tc_sync_factor_stage_mask) ||
        !config.game_load_composite_s3tc_sync_factor_stage_mask ||
        (config.game_load_composite_s3tc_sync_factor_stage_mask &
         ~TestSuite::Config::kAllGameLoadCompositeS3tcSyncFactorStages)) {
      errors.emplace_back(
          "game_load_composite.s3tc_sync_factor[stage_mask] must select bits 0 through 11");
      return false;
    }

    auto stages = json_getProperty(sync_factor, "stages");
    if (stages) {
      if (json_getType(stages) != JSON_OBJ) {
        errors.emplace_back(
            "game_load_composite.s3tc_sync_factor[stages] must be an object");
        return false;
      }
      uint32_t stage_list_mask = 0;
      for (auto stage = json_getChild(stages); stage;
           stage = json_getSibling(stage)) {
        const int index =
            GameLoadCompositeS3tcSyncFactorStageIndex(json_getName(stage));
        if (index < 0 || json_getType(stage) != JSON_BOOLEAN) {
          errors.emplace_back(
              "game_load_composite.s3tc_sync_factor[stages] contains an invalid stage/value");
          return false;
        }
        if (json_getBoolean(stage)) {
          stage_list_mask |= 1U << index;
        }
      }
      config.game_load_composite_s3tc_sync_factor_stage_mask &= stage_list_mask;
      if (!config.game_load_composite_s3tc_sync_factor_stage_mask) {
        errors.emplace_back("game_load_composite.s3tc_sync_factor selects no stages");
        return false;
      }
    }
  }
  return true;
}

bool RuntimeConfig::LoadConfigBuffer(const std::string& config_content, std::vector<std::string>& errors) {
  std::map<std::string, std::vector<std::string>> test_config;

  const JSONParser parser{config_content.c_str()};

  auto root = parser.root();
  if (!root) {
    errors.emplace_back("Failed to parse config file.");
    return false;
  }

  if (!ParseGameLoadCompositeConfig(root, test_suite_config_, errors)) {
    return false;
  }

  auto resolved_plan = json_getProperty(root, "resolved_plan");
  if (resolved_plan) {
    if (json_getType(resolved_plan) != JSON_OBJ) {
      errors.emplace_back("'resolved_plan' must be an object");
      return false;
    }
    uint32_t schema_version = 0;
    if (!LoadUint32(resolved_plan, "schema_version", schema_version) || schema_version != 2) {
      errors.emplace_back("resolved_plan[schema_version] must be 2");
      return false;
    }
    if (!LoadString(resolved_plan, "plan_id", plan_id_) || !IsSha256Id(plan_id_)) {
      errors.emplace_back("resolved_plan[plan_id] must be a lowercase sha256 identifier");
      return false;
    }
    std::string catalog_id;
    if (!LoadString(resolved_plan, "catalog_id", catalog_id) || catalog_id != TestCatalogId()) {
      errors.emplace_back("resolved_plan[catalog_id] does not match the bundled catalog");
      return false;
    }
    uint32_t declared_leaf_count = 0;
    if (!LoadUint32(resolved_plan, "selected_leaf_count", declared_leaf_count)) {
      errors.emplace_back("resolved_plan[selected_leaf_count] must be an integer");
      return false;
    }
    auto tests = json_getProperty(resolved_plan, "tests");
    if (!tests || json_getType(tests) != JSON_ARRAY) {
      errors.emplace_back("resolved_plan[tests] must be an array");
      return false;
    }
    test_suite_config_.game_load_composite_stage_mask = 0;
    test_suite_config_.game_load_composite_cross_title_stage_mask = 0;
    test_suite_config_.game_load_composite_s3tc_sync_factor_stage_mask = 0;
    uint32_t memory_pressure_representative_mask = 0;
    uint32_t memory_pressure_stress_mask = 0;
    for (auto test = json_getChild(tests); test; test = json_getSibling(test)) {
      if (json_getType(test) != JSON_OBJ) {
        errors.emplace_back("resolved_plan[tests] entries must be objects");
        return false;
      }
      std::string id;
      if (!LoadString(test, "id", id) || id.empty()) {
        errors.emplace_back("resolved_plan test id must be a non-empty string");
        return false;
      }
      const auto *descriptor = FindTestDescriptorById(id);
      if (!descriptor) {
        errors.emplace_back("resolved_plan contains unknown test id: " + id);
        return false;
      }
      if (descriptor->kind != TestKind::LEAF) {
        errors.emplace_back("resolved_plan must contain leaf ids, not group id: " + id);
        return false;
      }
      if (!selected_test_ids_.insert(id).second) {
        errors.emplace_back("resolved_plan contains duplicate test id: " + id);
        return false;
      }
      const uint32_t bit = 1U << descriptor->selection_bit;
      switch (static_cast<TestSelectionGroup>(descriptor->selection_group)) {
        case TestSelectionGroup::LONG_SCENE:
          test_suite_config_.game_load_composite_stage_mask |= bit;
          break;
        case TestSelectionGroup::CROSS_TITLE:
          test_suite_config_.game_load_composite_cross_title_stage_mask |= bit;
          break;
        case TestSelectionGroup::S3TC_SYNC_FACTOR:
          test_suite_config_.game_load_composite_s3tc_sync_factor_stage_mask |= bit;
          break;
        case TestSelectionGroup::MEMORY_PRESSURE_REPRESENTATIVE:
          memory_pressure_representative_mask |= bit;
          break;
        case TestSelectionGroup::MEMORY_PRESSURE_STRESS:
          memory_pressure_stress_mask |= bit;
          break;
        case TestSelectionGroup::NONE:
          break;
      }
    }
    selected_leaf_count_ = static_cast<uint32_t>(selected_test_ids_.size());
    if (!selected_leaf_count_ || selected_leaf_count_ != declared_leaf_count) {
      errors.emplace_back("resolved_plan[selected_leaf_count] does not match its unique leaf ids");
      return false;
    }
    static constexpr uint32_t kAllMemoryPressureCheckpoints = 0x1F;
    if ((memory_pressure_representative_mask &&
         memory_pressure_representative_mask != kAllMemoryPressureCheckpoints) ||
        (memory_pressure_stress_mask && memory_pressure_stress_mask != kAllMemoryPressureCheckpoints)) {
      errors.emplace_back("memory-pressure plans must include all five checkpoint leaf ids");
      return false;
    }
    has_resolved_plan_ = true;
  }

  auto settings = json_getProperty(root, "settings");
  if (!settings) {
    if (!has_resolved_plan_) {
      errors.emplace_back("'settings' not found");
      return false;
    }
  } else if (json_getType(settings) != JSON_OBJ) {
    errors.emplace_back("'settings' not an object");
    return false;
  }
  if (!settings) {
    settings = root;
  }

  if (!LoadBool(settings, "disable_autorun", disable_autorun_)) {
    errors.emplace_back("settings[disable_autorun] must be a boolean");
    return false;
  }

  if (!LoadBool(settings, "enable_autorun_immediately", enable_autorun_immediately_)) {
    errors.emplace_back("settings[enable_autorun_immediately] must be a boolean");
    return false;
  }

  if (!LoadBool(settings, "enable_shutdown_on_completion", enable_shutdown_on_completion_)) {
    errors.emplace_back("settings[enable_shutdown_on_completion] must be a boolean");
    return false;
  }

  if (!LoadBool(settings, "skip_tests_by_default", skip_tests_by_default_)) {
    errors.emplace_back("settings[skip_tests_by_default] must be a boolean");
    return false;
  }

  if (!LoadString(settings, "output_directory_path", output_directory_path_)) {
    errors.emplace_back("settings[output_directory_path] must be a string");
    return false;
  }
  output_directory_path_ = SanitizePath(output_directory_path_);

  if (!LoadUint32(settings, "reboot_or_shutdown_delay", reboot_or_shutdown_delay_ms_)) {
    errors.emplace_back("settings[reboot_or_shutdown_delay] must be an integer");
    return false;
  }

  if (!LoadUint32(settings, "warmup_iterations", warmup_iterations_)) {
    errors.emplace_back("settings[warmup_iterations] must be an integer");
    return false;
  }

  if (!LoadUint32(settings, "measurement_iterations_multiplier", measurement_iterations_multiplier_) ||
      measurement_iterations_multiplier_ < 1 || measurement_iterations_multiplier_ > 100000) {
    errors.emplace_back("settings[measurement_iterations_multiplier] must be an integer from 1 through 100000");
    return false;
  }

  std::string gpu_completion_mode;
  if (!LoadString(settings, "gpu_completion_mode", gpu_completion_mode)) {
    errors.emplace_back("settings[gpu_completion_mode] must be a string");
    return false;
  }
  if (!gpu_completion_mode.empty()) {
    if (gpu_completion_mode == "enqueue") {
      gpu_completion_mode_ = TestHost::GpuCompletionMode::ENQUEUE;
    } else if (gpu_completion_mode == "batch_complete") {
      gpu_completion_mode_ = TestHost::GpuCompletionMode::BATCH_COMPLETE;
    } else if (gpu_completion_mode == "per_iteration") {
      gpu_completion_mode_ = TestHost::GpuCompletionMode::PER_ITERATION;
    } else {
      errors.emplace_back(
          "settings[gpu_completion_mode] must be enqueue, batch_complete, or per_iteration");
      return false;
    }
  }

  auto test_suites = json_getProperty(root, "test_suites");
  if (!test_suites) {
    return true;
  }

  if (has_resolved_plan_) {
    errors.emplace_back("resolved_plan and legacy test_suites filtering cannot be combined");
    return false;
  }

  if (json_getType(test_suites) != JSON_OBJ) {
    errors.emplace_back("'test_suites' not an object");
    return false;
  }

  return ParseTestSuites(test_suites, errors, configured_test_suites_, configured_test_cases_);
}

static RuntimeConfig::SkipConfiguration MakeSkipConfiguration(bool is_skipped) {
  if (is_skipped) {
    return RuntimeConfig::SkipConfiguration::SKIPPED;
  }
  return RuntimeConfig::SkipConfiguration::UNSKIPPED;
}

static bool ParseTestCase(json_t const* test_case, const std::string& suite_name, const std::string& test_name,
                          std::vector<std::string>& errors, RuntimeConfig::SkipConfiguration& config_value,
                          const std::string& test_case_error_message_prefix) {
  for (auto element = json_getChild(test_case); element; element = json_getSibling(element)) {
    std::string name = json_getName(element);
    auto type = json_getType(element);

    if (name != "skipped") {
      errors.emplace_back(test_case_error_message_prefix + "[" + name + "] unsupported. Ignoring");
      continue;
    }

    if (type == JSON_BOOLEAN) {
      config_value = MakeSkipConfiguration(json_getBoolean(element));
    } else {
      errors.emplace_back(test_case_error_message_prefix + "[skipped] must be a boolean");
      return false;
    }
  }

  return true;
}

static bool ParseTestCases(
    json_t const* test_suite, const std::string& suite_name, std::vector<std::string>& errors,
    std::map<std::string, RuntimeConfig::SkipConfiguration>& configured_suites,
    std::map<std::string, std::map<std::string, RuntimeConfig::SkipConfiguration>>& configured_cases,
    const std::string& suite_error_message_prefix) {
  std::map<std::string, RuntimeConfig::SkipConfiguration> case_settings;

  for (auto test_or_skipped = json_getChild(test_suite); test_or_skipped;
       test_or_skipped = json_getSibling(test_or_skipped)) {
    std::string test_name = json_getName(test_or_skipped);
    auto type = json_getType(test_or_skipped);

    if (test_name == "skipped") {
      if (type == JSON_BOOLEAN) {
        configured_suites[suite_name] = MakeSkipConfiguration(json_getBoolean(test_or_skipped));
        continue;
      }

      errors.emplace_back(suite_error_message_prefix + "[skipped] must be a boolean.");
      return false;
    }

    if (type == JSON_OBJ) {
      auto config_value = RuntimeConfig::SkipConfiguration::DEFAULT;
      if (!ParseTestCase(test_or_skipped, suite_name, test_name, errors, config_value,
                         suite_error_message_prefix + "[" + test_name + "]")) {
        return false;
      }
      if (config_value != RuntimeConfig::SkipConfiguration::DEFAULT) {
        case_settings[test_name] = config_value;
      }
    } else {
      errors.emplace_back(suite_error_message_prefix + "[" + test_name + "] must be an object. Ignoring");
      continue;
    }
  }

  if (!case_settings.empty()) {
    configured_cases[suite_name] = case_settings;
  }

  return true;
}

static bool ParseTestSuites(
    json_t const* test_suites, std::vector<std::string>& errors,
    std::map<std::string, RuntimeConfig::SkipConfiguration>& skipped_test_suites,
    std::map<std::string, std::map<std::string, RuntimeConfig::SkipConfiguration>>& skipped_test_cases) {
  std::string test_suites_error_message_prefix("test_suites[");
  for (auto suite = json_getChild(test_suites); suite; suite = json_getSibling(suite)) {
    std::string suite_name = json_getName(suite);
    auto suite_error_message_prefix = test_suites_error_message_prefix + suite_name + "]";

    if (json_getType(suite) != JSON_OBJ) {
      errors.emplace_back(suite_error_message_prefix + " must be an object. Ignoring");
      continue;
    }

    if (!ParseTestCases(suite, suite_name, errors, skipped_test_suites, skipped_test_cases,
                        suite_error_message_prefix)) {
      return false;
    }
  }

  return true;
}

bool RuntimeConfig::ApplyConfig(std::vector<std::shared_ptr<TestSuite>>& test_suites,
                                std::vector<std::string>& errors) {
  std::vector<std::shared_ptr<TestSuite>> filtered_test_suites;

  if (has_resolved_plan_) {
    std::map<std::string, std::set<std::string>> enabled_execution_tests;
    for (const auto &id : selected_test_ids_) {
      const auto *descriptor = FindTestDescriptorById(id);
      ASSERT(descriptor && descriptor->kind == TestKind::LEAF);
      enabled_execution_tests[descriptor->legacy_suite].insert(descriptor->execution_test);
    }
    for (auto &suite : test_suites) {
      std::set<std::string> disabled;
      const auto enabled = enabled_execution_tests.find(suite->Name());
      for (const auto &test_name : suite->TestNames()) {
        if (enabled == enabled_execution_tests.end() || !enabled->second.count(test_name)) {
          disabled.insert(test_name);
        }
      }
      suite->DisableTests(disabled);
      if (suite->HasEnabledTests()) {
        filtered_test_suites.push_back(suite);
      }
    }
    test_suites = filtered_test_suites;
    return true;
  }

  for (auto& suite : test_suites) {
    auto default_skip_test_case = skip_tests_by_default_;

    auto entry = configured_test_suites_.find(suite->Name());
    if (entry != configured_test_suites_.end()) {
      switch (entry->second) {
        case SkipConfiguration::SKIPPED:
          default_skip_test_case = true;
          break;
        case SkipConfiguration::UNSKIPPED:
          default_skip_test_case = false;
          break;
        default:
          break;
      }
    }

    auto test_case_config = configured_test_cases_.find(suite->Name());
    std::set<std::string> skipped_test_cases;

    for (auto& test_case : suite->TestNames()) {
      bool skip_test_case = default_skip_test_case;

      if (test_case_config != configured_test_cases_.end()) {
        auto explicit_config = test_case_config->second.find(test_case);
        if (explicit_config != test_case_config->second.end()) {
          skip_test_case = explicit_config->second == SkipConfiguration::SKIPPED;
        }
      }

      if (skip_test_case) {
        skipped_test_cases.insert(test_case);
      }
    }

    if (!skipped_test_cases.empty()) {
      suite->DisableTests(skipped_test_cases);
    }

    if (suite->HasEnabledTests()) {
      filtered_test_suites.push_back(suite);
    }
  }

  test_suites = filtered_test_suites;

  return true;
}

std::string RuntimeConfig::SanitizePath(const std::string& path) {
  std::string sanitized(path);
  std::replace(sanitized.begin(), sanitized.end(), '/', '\\');
  return std::move(sanitized);
}
