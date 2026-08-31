#include "menu_item.h"

#include <pbkit/pbkit.h>

#include <chrono>
#include <cstdio>
#include <map>
#include <memory>
#include <utility>

#include "configure.h"
#include "debug_output.h"
#include "device_info.h"
#include "pushbuffer.h"
#include "result_store.h"
#include "tests/test_suite.h"
#include "test_catalog.h"

using namespace PBKitPlusPlus;

static constexpr uint32_t kAutoTestAllTimeoutMilliseconds = 3000;
static constexpr uint32_t kNumItemsPerPage = 12;
static constexpr uint32_t kNumItemsPerHalfPage = kNumItemsPerPage >> 1;

uint32_t MenuItem::menu_background_color_ = 0xFF3E003E;
MenuItemTest::RunMode MenuItemTest::run_mode_ = RunMode::SINGLE_FRAME;

void MenuItem::PrepareDraw(uint32_t background_color) const {
  pb_wait_for_vbl();
  pb_target_back_buffer();
  Pushbuffer::Flush();
  pb_fill(0, 0, width, height, background_color);
  pb_erase_text_screen();
}

void MenuItem::Swap() {
  pb_draw_text_screen();
  while (pb_busy()) {
    /* Wait for completion... */
  }

  /* Swap buffers (if we can) */
  while (pb_finished()) {
    /* Not ready to swap yet */
  }
}

void MenuItem::Draw() {
  if (active_submenu) {
    active_submenu->Draw();
    return;
  }

  PrepareDraw(menu_background_color_);

  if (!header.empty()) {
    pb_print("%s\n", header.c_str());
  }

  const char *cursor_prefix = "> ";
  const char *normal_prefix = "  ";
  const char *cursor_suffix = " <";
  const char *normal_suffix = "";

  uint32_t i = 0;
  if (cursor_position > kNumItemsPerHalfPage) {
    i = cursor_position - kNumItemsPerHalfPage;
    if (i + kNumItemsPerPage > submenu.size()) {
      if (submenu.size() < kNumItemsPerPage) {
        i = 0;
      } else {
        i = submenu.size() - kNumItemsPerPage;
      }
    }
  }

  if (i) {
    pb_print("...\n");
  }

  uint32_t i_end = i + std::min(kNumItemsPerPage, submenu.size());

  for (; i < i_end; ++i) {
    const char *prefix = i == cursor_position ? cursor_prefix : normal_prefix;
    const char *suffix = i == cursor_position ? cursor_suffix : normal_suffix;
    pb_print("%s%s%s\n", prefix, submenu[i]->name.c_str(), suffix);
  }

  if (i_end < submenu.size()) {
    pb_print("...\n");
  }

  if (!footer.empty()) {
    pb_print("\n%s\n", footer.c_str());
  }

  Swap();
}

void MenuItem::OnEnter() {}

void MenuItem::Activate() {
  if (active_submenu) {
    active_submenu->Activate();
    return;
  }

  if (submenu.empty()) {
    return;
  }
  auto activated_item = submenu[cursor_position];
  if (activated_item->IsEnterable()) {
    active_submenu = activated_item;
    activated_item->OnEnter();
  } else {
    activated_item->Activate();
  }
}

void MenuItem::ActivateCurrentSuite() {
  if (active_submenu) {
    active_submenu->ActivateCurrentSuite();
    return;
  }
  if (submenu.empty()) {
    return;
  }
  auto activated_item = submenu[cursor_position];
  activated_item->ActivateCurrentSuite();
}

bool MenuItem::Deactivate() {
  if (!active_submenu) {
    return false;
  }

  bool was_submenu_activated = active_submenu->Deactivate();
  if (!was_submenu_activated) {
    active_submenu.reset();
  }
  return true;
}

void MenuItem::CursorUp(bool is_repeat) {
  if (active_submenu) {
    active_submenu->CursorUp(is_repeat);
    return;
  }

  if (submenu.empty()) {
    return;
  }
  if (cursor_position > 0) {
    --cursor_position;
  } else {
    cursor_position = submenu.size() - 1;
  }
}

void MenuItem::CursorDown(bool is_repeat) {
  if (active_submenu) {
    active_submenu->CursorDown(is_repeat);
    return;
  }

  if (submenu.empty()) {
    return;
  }
  if (cursor_position < submenu.size() - 1) {
    ++cursor_position;
  } else {
    cursor_position = 0;
  }
}

void MenuItem::CursorLeft(bool is_repeat) {
  if (active_submenu) {
    active_submenu->CursorLeft(is_repeat);
    return;
  }

  if (cursor_position > kNumItemsPerHalfPage) {
    cursor_position -= kNumItemsPerHalfPage;
  } else {
    cursor_position = 0;
  }
}

void MenuItem::CursorRight(bool is_repeat) {
  if (active_submenu) {
    active_submenu->CursorRight(is_repeat);
    return;
  }

  if (submenu.empty()) {
    return;
  }
  cursor_position += kNumItemsPerHalfPage;
  if (cursor_position >= submenu.size()) {
    cursor_position = submenu.size() - 1;
  }
}

void MenuItem::CursorUpAndActivate() {
  active_submenu->Deactivate();
  active_submenu = nullptr;
  CursorUp(false);
  Activate();
}

void MenuItem::CursorDownAndActivate() {
  active_submenu->Deactivate();
  active_submenu = nullptr;
  CursorDown(false);
  Activate();
}

void MenuItem::SetBackgroundColor(uint32_t background_color) { menu_background_color_ = background_color; }

MenuItemInfo::MenuItemInfo(std::string name, std::vector<std::string> lines,
                           uint32_t width, uint32_t height,
                           std::function<void()> on_activate)
    : MenuItem(std::move(name), width, height), lines_(std::move(lines)),
      on_activate_(std::move(on_activate)) {}

MenuItemInfo::MenuItemInfo(
    std::string name, std::function<std::vector<std::string>()> poll_lines,
    uint32_t width, uint32_t height)
    : MenuItem(std::move(name), width, height),
      poll_lines_(std::move(poll_lines)) {}

void MenuItemInfo::OnEnter() {
  if (poll_lines_) {
    lines_ = poll_lines_();
  }
}

void MenuItemInfo::Draw() {
  PrepareDraw(menu_background_color_);
  pb_print("%s\n\n", name.c_str());
  for (const auto &line : lines_) {
    pb_print("%s\n", line.c_str());
  }
  const char *controls = "B/Back: return";
  if (poll_lines_) {
    controls = "A: refresh   B/Back: return";
  } else if (on_activate_) {
    controls = "A: run route   B/Back: return";
  }
  pb_print("\n%s\n", controls);
  Swap();
}

void MenuItemInfo::Activate() {
  if (poll_lines_) {
    lines_ = poll_lines_();
    return;
  }
  if (on_activate_) {
    on_activate_();
  }
}

namespace {

std::string FormatResultTime(const char *label, uint32_t microseconds) {
  char text[80] = {};
  snprintf(text, sizeof(text), "%s: %lu.%03lu ms", label,
           static_cast<unsigned long>(microseconds / 1000),
           static_cast<unsigned long>(microseconds % 1000));
  return text;
}

std::string FormatResultSize(uint64_t bytes) {
  char text[80] = {};
  snprintf(text, sizeof(text), "Size: %llu bytes",
           static_cast<unsigned long long>(bytes));
  return text;
}

}  // namespace

MenuItemStoredResultFile::MenuItemStoredResultFile(
    std::string path, std::string label, uint32_t width, uint32_t height)
    : MenuItem(std::move(label), width, height), path_(std::move(path)) {
  header = "Saved result: " + name;
  footer = "A details  B return  Left/Right page";
}

void MenuItemStoredResultFile::OnEnter() {
  submenu.clear();
  cursor_position = 0;
  const StoredResultFile file = ReadStoredResults(path_);
  uint32_t leaf_count = 0;
  uint32_t group_count = 0;
  uint32_t failure_count = 0;
  for (const auto &record : file.records) {
    if (record.kind == "group") {
      ++group_count;
    } else {
      ++leaf_count;
    }
    if (record.oracle_failed || record.outcome == "FAIL") {
      ++failure_count;
    }
  }

  char counts[96] = {};
  snprintf(counts, sizeof(counts), "Leaves: %lu  Groups: %lu  Failures: %lu",
           static_cast<unsigned long>(leaf_count),
           static_cast<unsigned long>(group_count),
           static_cast<unsigned long>(failure_count));
  std::vector<std::string> summary{
      std::string("Completion: ") + (file.complete ? "COMPLETE" : "INCOMPLETE"),
      counts, FormatResultSize(file.size_bytes), "Path: " + file.path};
  if (!file.error.empty()) {
    summary.emplace_back("Error: " + file.error);
  }
  auto summary_item = std::make_shared<MenuItemInfo>(
      "Run summary", std::move(summary), width, height);
  summary_item->parent = this;
  submenu.push_back(summary_item);

  for (const auto &record : file.records) {
    std::vector<std::string> lines{
        "ID: " + record.id,
        "Legacy: " + record.name,
        "Kind: " + record.kind,
        "Outcome: " + record.outcome};
    if (record.has_measurement) {
      lines.push_back(FormatResultTime("Average", record.average_us));
      lines.push_back(FormatResultTime("Minimum", record.minimum_us));
      lines.push_back(FormatResultTime("Maximum", record.maximum_us));
    } else {
      lines.emplace_back("Measurement: none");
    }
    lines.emplace_back(std::string("Oracle: ") +
                       (record.oracle_failed ? "FAIL" : "no recorded failure"));
    const std::string label = record.id.empty() ? record.name : record.id;
    auto item = std::make_shared<MenuItemInfo>(label, std::move(lines), width,
                                               height);
    item->parent = this;
    submenu.push_back(item);
  }
}

MenuItemStoredResults::MenuItemStoredResults(std::string output_directory,
                                             uint32_t width, uint32_t height)
    : MenuItem("Previous results", width, height),
      output_directory_(std::move(output_directory)) {
  header = "Saved benchmark runs";
  footer = "A open  B return  Left/Right page";
}

void MenuItemStoredResults::OnEnter() {
  submenu.clear();
  cursor_position = 0;
  const auto paths = DiscoverStoredResults(output_directory_);
  if (paths.empty()) {
    auto empty = std::make_shared<MenuItemInfo>(
        "No saved results",
        std::vector<std::string>{"Run a test first.",
                                 "Results are saved under:",
                                 output_directory_},
        width, height);
    empty->parent = this;
    submenu.push_back(empty);
    return;
  }
  for (const auto &path : paths) {
    const auto slash = path.find_last_of("\\/");
    const std::string label =
        slash == std::string::npos ? path : path.substr(slash + 1);
    auto item = std::make_shared<MenuItemStoredResultFile>(
        path, label, width, height);
    item->parent = this;
    submenu.push_back(item);
  }
}

MenuItemCallable::MenuItemCallable(std::function<void()> callback, std::string name, uint32_t width, uint32_t height)
    : MenuItem(std::move(name), width, height), on_activate(std::move(callback)) {}

void MenuItemCallable::Draw() {}

void MenuItemCallable::Activate() { on_activate(); }

MenuItemTest::MenuItemTest(std::shared_ptr<TestSuite> suite, std::string name, uint32_t width, uint32_t height)
    : MenuItem(std::move(name), width, height), suite(std::move(suite)) {}

void MenuItemTest::Draw() {
  if (run_mode_ == RunMode::SINGLE_FRAME && frame_count) {
    return;
  }

  suite->Run(name, frame_count++);
}

void MenuItemTest::OnEnter() {
  // Blank the screen.
  PrepareDraw(0xFF000000);
  pb_print("Running %s", name.c_str());
  Swap();

  if (frame_count) {
    suite->Deinitialize();
  }
  suite->Initialize();
  frame_count = 0;
}

bool MenuItemTest::Deactivate() {
  suite->Deinitialize();
  frame_count = 0;
  return MenuItem::Deactivate();
}

void MenuItemTest::CursorUp(bool is_repeat) {
  if (!is_repeat) {
    parent->CursorUpAndActivate();
  }
}

void MenuItemTest::CursorDown(bool is_repeat) {
  if (!is_repeat) {
    parent->CursorDownAndActivate();
  }
}

void MenuItemTest::CursorLeft(bool is_repeat) { suite->UpdateUserContext(-1); }

void MenuItemTest::CursorRight(bool is_repeat) { suite->UpdateUserContext(+1); }

MenuItemSuite::MenuItemSuite(const std::shared_ptr<TestSuite> &suite, uint32_t width, uint32_t height)
    : MenuItem(suite->Name(), width, height), suite(suite) {
  auto tests = suite->TestNames();
  submenu.reserve(tests.size());

  for (auto &test : tests) {
    auto child = std::make_shared<MenuItemTest>(suite, test, width, height);
    child->parent = this;
    submenu.push_back(child);
  }
}

void MenuItemSuite::ActivateCurrentSuite() {
  suite->Initialize();
  suite->RunAll();
  suite->Deinitialize();
  MenuItem::Deactivate();
}

MenuItemRoot::MenuItemRoot(const std::vector<std::shared_ptr<TestSuite>> &suites, std::function<void()> on_run_all,
                           std::function<void()> on_exit,
                           std::function<void(const TestDescriptor &)> on_run_catalog_route,
                           uint32_t width, uint32_t height, bool disable_autorun,
                           bool autorun_immediately, const std::string &active_plan,
                           const std::string &output_directory)
    : MenuItem("<<root>>", width, height),
      on_run_all(std::move(on_run_all)),
      on_exit(std::move(on_exit)),
      disable_autorun_(disable_autorun),
      autorun_immediately_(autorun_immediately) {
  char inventory[160] = {};
  snprintf(inventory, sizeof(inventory),
           "Catalog: %lu tests, %lu groups, %lu aliases",
           static_cast<unsigned long>(TestCatalogLeafCount()),
           static_cast<unsigned long>(TestCatalogGroupCount()),
           static_cast<unsigned long>(TestCatalogLegacyAliasCount()));
  header = "xemu perf tests | " + active_plan;
  footer = "A/Start select  B/Back return  X run suite  Black exit";
  if (!disable_autorun) {
    submenu.push_back(std::make_shared<MenuItemCallable>(on_run_all, "Run all and exit", width, height));
  }

  auto stored_results = std::make_shared<MenuItemStoredResults>(
      output_directory, width, height);
  stored_results->parent = this;
  submenu.push_back(stored_results);

  auto device_info = std::make_shared<MenuItemInfo>(
      "System information",
      [output_directory, width, height]() {
        return PollDeviceInfo(output_directory, width, height);
      },
      width, height);
  device_info->parent = this;
  submenu.push_back(device_info);

  submenu.push_back(std::make_shared<MenuItemInfo>(
      "About / controls",
      std::vector<std::string>{inventory, "Catalog ID:", TestCatalogId(),
                               "Results: E:\\xemu_perf_tests\\results.txt",
                               "Green=single run; red=continuous (Y toggles).",
                               "Catalog entries run their mapped execution route."},
      width, height));

  auto plans = std::make_shared<MenuItem>("Plans", width, height);
  plans->SetHeader("On-disc plans (mapped execution routes)");
  plans->SetFooter("A run plan  B return");
  auto add_plan = [plans, width, height, on_run_catalog_route](
                      const char *name, std::vector<std::string> ids) {
    plans->submenu.push_back(std::make_shared<MenuItemCallable>(
        [on_run_catalog_route, ids]() {
          for (const auto &id : ids) {
            const auto *descriptor = FindTestDescriptorById(id);
            if (descriptor) {
              on_run_catalog_route(*descriptor);
            }
          }
        },
        name, width, height));
  };
  plans->submenu.push_back(std::make_shared<MenuItemCallable>(
      on_run_all, "Active selection: run all and exit", width, height));
  add_plan("Quick smoke routes", {"busy_pfifo.pgraph_pattern_polling",
                                   "surface.cpu_read_clean_surface",
                                   "game_load.s3tc_sync_factor"});
  add_plan("S3TC / BC texture matrix", {"game_load.s3tc_sync_factor"});
  add_plan("Vulkan memory: representative",
           {"surface.vulkan_memory_pressure.representative"});
  add_plan("Vulkan memory: stress", {"surface.vulkan_memory_pressure.stress"});
  plans->parent = this;
  submenu.push_back(plans);

  for (auto &suite : suites) {
    auto child = std::make_shared<MenuItemSuite>(suite, width, height);
    child->parent = this;
    child->SetHeader("Suite: " + suite->Name());
    child->SetFooter("A run test  X run suite  B return  Left/Right page");
    submenu.push_back(child);
  }

  auto catalog_root = std::make_shared<MenuItem>("Catalog browser", width, height);
  catalog_root->SetHeader("Catalog browser: stable test and group IDs");
  catalog_root->SetFooter("A details  B return  Left/Right page");
  std::map<std::string, std::shared_ptr<MenuItem>> catalog_suites;
  for (const auto *descriptor : TestCatalogEntries()) {
    std::shared_ptr<TestSuite> route_suite;
    for (const auto &suite : suites) {
      if (suite->Name() == descriptor->legacy_suite && suite->HasTest(descriptor->execution_test)) {
        route_suite = suite;
        break;
      }
    }
    // A resolved plan may remove execution routes. Only advertise routes that
    // this boot can actually execute.
    if (!route_suite) {
      continue;
    }
    auto &suite_menu = catalog_suites[descriptor->suite_id];
    if (!suite_menu) {
      suite_menu = std::make_shared<MenuItem>(descriptor->suite_id, width, height);
      suite_menu->SetHeader("Catalog suite: " + std::string(descriptor->suite_id));
      suite_menu->SetFooter("A details  B return  Left/Right page");
      suite_menu->parent = catalog_root.get();
      catalog_root->submenu.push_back(suite_menu);
    }
    std::vector<std::string> lines{
        std::string("ID: ") + descriptor->id,
        std::string("Kind: ") + (descriptor->kind == TestKind::LEAF ? "test" : "group"),
        std::string("Legacy: ") + descriptor->legacy_suite + "::" + descriptor->legacy_result,
        std::string("Route: ") + descriptor->legacy_suite + "::" + descriptor->execution_test,
        descriptor->description};
    if (descriptor->selection_group != 0) {
      lines.emplace_back("Grouped route: running it may emit sibling stages.");
    }
    auto entry = std::make_shared<MenuItemInfo>(
        descriptor->display_name, std::move(lines), width, height,
        [on_run_catalog_route, descriptor]() { on_run_catalog_route(*descriptor); });
    entry->parent = suite_menu.get();
    suite_menu->submenu.push_back(entry);
  }
  catalog_root->parent = this;
  submenu.push_back(catalog_root);

  if (disable_autorun) {
    submenu.push_back(std::make_shared<MenuItemCallable>(on_run_all, "! Run all and exit", width, height));
  }
}

void MenuItemRoot::ActivateCurrentSuite() {
  timer_cancelled = true;
  MenuItem::ActivateCurrentSuite();
}

void MenuItemRoot::Draw() {
  if (!timer_valid) {
    start_time = std::chrono::high_resolution_clock::now();
    timer_valid = true;
  }

  if (!disable_autorun_) {
    if (!timer_cancelled) {
      auto now = std::chrono::high_resolution_clock::now();
      auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count();

      if (autorun_immediately_ || elapsed > kAutoTestAllTimeoutMilliseconds) {
        on_run_all();
        return;
      }

      char run_all[128] = {0};
      snprintf(run_all, 127, "Run all and exit (automatic in %d ms)", kAutoTestAllTimeoutMilliseconds - elapsed);
      submenu[0]->name = run_all;
    } else {
      submenu[0]->name = "Run all and exit";
    }
  }

  MenuItem::Draw();
}

void MenuItemRoot::Activate() {
  timer_cancelled = true;
  MenuItem::Activate();
}

bool MenuItemRoot::Deactivate() {
  timer_cancelled = true;
  if (!active_submenu) {
    on_exit();
    return false;
  }

  return MenuItem::Deactivate();
}

void MenuItemRoot::CursorUp(bool is_repeat) {
  timer_cancelled = true;
  MenuItem::CursorUp(is_repeat);
}

void MenuItemRoot::CursorDown(bool is_repeat) {
  timer_cancelled = true;
  MenuItem::CursorDown(is_repeat);
}

void MenuItemRoot::CursorLeft(bool is_repeat) {
  timer_cancelled = true;
  MenuItem::CursorLeft(is_repeat);
}

void MenuItemRoot::CursorRight(bool is_repeat) {
  timer_cancelled = true;
  MenuItem::CursorRight(is_repeat);
}

struct MenuItemOption : public MenuItem {
  MenuItemOption(const std::string &name, std::function<void(const MenuItemOption &)> on_apply);
  MenuItemOption(const std::string &label, const std::vector<std::string> &values,
                 std::function<void(const MenuItemOption &)> on_apply);

  inline void UpdateName() { name = label + ": " + values[current_option]; }

  void Activate() override;
  void CursorLeft(bool is_repeat) override;
  void CursorRight(bool is_repeat) override;

  std::string label;
  std::vector<std::string> values;
  uint32_t current_option = 0;

  std::function<void(const MenuItemOption &)> on_apply;
};

MenuItemOption::MenuItemOption(const std::string &name, std::function<void(const MenuItemOption &)> on_apply)
    : MenuItem(name, 0, 0), on_apply(on_apply) {}

MenuItemOption::MenuItemOption(const std::string &label, const std::vector<std::string> &values,
                               std::function<void(const MenuItemOption &)> on_apply)
    : MenuItem("", 0, 0), label(label), values(values), on_apply(on_apply) {
  ASSERT(!values.empty())
  UpdateName();
}

void MenuItemOption::Activate() {
  current_option = (current_option + 1) % values.size();
  UpdateName();
}

void MenuItemOption::CursorLeft(bool is_repeat) {
  current_option = (current_option - 1) % values.size();
  UpdateName();
}

void MenuItemOption::CursorRight(bool is_repeat) { Activate(); }

MenuItemOptions::MenuItemOptions(const std::vector<std::shared_ptr<TestSuite>> &suites, std::function<void()> on_exit,
                                 uint32_t width, uint32_t height)
    : MenuItem("<<options>>", width, height), on_exit(std::move(on_exit)) {
  submenu.push_back(
      std::make_shared<MenuItemOption>("Accept", [this](const MenuItemOption &_ignored) { this->on_exit(); }));
}

void MenuItemOptions::Draw() {
  if (!timer_valid) {
    start_time = std::chrono::high_resolution_clock::now();
    timer_valid = true;
  }
  if (!timer_cancelled) {
    auto now = std::chrono::high_resolution_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count();
    if (elapsed > kAutoTestAllTimeoutMilliseconds) {
      cursor_position = 0;
      Activate();
      return;
    }

    char run_all[128] = {0};
    snprintf(run_all, 127, "Accept (automatic in %d ms)", kAutoTestAllTimeoutMilliseconds - elapsed);
    submenu[0]->name = run_all;
  } else {
    submenu[0]->name = "Accept";
  }

  MenuItem::Draw();
}

void MenuItemOptions::Activate() {
  timer_cancelled = true;
  if (cursor_position == 0) {
    for (auto i = 1; i < submenu.size(); ++i) {
      const auto &item = *(reinterpret_cast<MenuItemOption *>(submenu[i].get()));
      item.on_apply(item);
    }
    on_exit();
    return;
  }
  MenuItem::Activate();
}
void MenuItemOptions::ActivateCurrentSuite() {
  timer_cancelled = true;
  MenuItem::ActivateCurrentSuite();
}

bool MenuItemOptions::Deactivate() {
  timer_cancelled = true;
  on_exit();
  return false;
}

void MenuItemOptions::CursorUp(bool is_repeat) {
  timer_cancelled = true;
  MenuItem::CursorUp(is_repeat);
}

void MenuItemOptions::CursorDown(bool is_repeat) {
  timer_cancelled = true;
  MenuItem::CursorDown(is_repeat);
}

void MenuItemOptions::CursorLeft(bool is_repeat) {
  timer_cancelled = true;
  if (cursor_position > 0) {
    submenu[cursor_position]->CursorLeft(is_repeat);
  }
}

void MenuItemOptions::CursorRight(bool is_repeat) {
  timer_cancelled = true;
  if (cursor_position > 0) {
    submenu[cursor_position]->CursorRight(is_repeat);
  }
}
