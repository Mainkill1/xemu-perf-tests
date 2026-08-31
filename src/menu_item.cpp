#include "menu_item.h"

#include <pbkit/pbkit.h>

#include <chrono>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <map>
#include <memory>
#include <utility>

#include "configure.h"
#include "debug_output.h"
#include "device_info.h"
#include "pushbuffer.h"
#include "result_store.h"
#include "result_statistics.h"
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

bool MenuItem::HandleX() {
  return active_submenu ? active_submenu->HandleX() : false;
}

bool MenuItem::HandleY() {
  return active_submenu ? active_submenu->HandleY() : false;
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

std::string g_result_baseline_path;

constexpr uint32_t kViewerBackground = 0xFF07110D;
constexpr uint32_t kViewerPanel = 0xFF0E2118;
constexpr uint32_t kViewerPanelBorder = 0xFF153525;
constexpr uint32_t kViewerAccent = 0xFF58CF87;
constexpr uint32_t kViewerInfo = 0xFF62B8C4;
constexpr uint32_t kViewerWarning = 0xFFDFB45D;
constexpr uint32_t kViewerFailure = 0xFFDD6A64;

constexpr int kPlotLeft = 40;
constexpr int kPlotTop = 190;
constexpr int kPlotWidth = 560;
constexpr int kPlotHeight = 210;
// Histogram density follows the visible width. Eight pixels keeps every bar
// legible on 480i output; it is not a workload or data retention limit.
constexpr int kMinimumHistogramBarWidth = 8;

std::string FormatResultSize(uint64_t bytes) {
  char text[80] = {};
  snprintf(text, sizeof(text), "Size: %llu bytes",
           static_cast<unsigned long long>(bytes));
  return text;
}

std::string FormatResultCompact(const char *label, uint32_t microseconds,
                                bool approximate = false) {
  char text[96] = {};
  snprintf(text, sizeof(text), "%s%s %lu.%03lu ms", label,
           approximate ? "~" : "",
           static_cast<unsigned long>(microseconds / 1000),
           static_cast<unsigned long>(microseconds % 1000));
  return text;
}

bool IsFailure(const StoredResultRecord &record) {
  return record.oracle_failed || record.outcome == "FAIL";
}

uint32_t ScaleGraphY(uint32_t value, uint32_t minimum, uint32_t maximum) {
  if (maximum <= minimum) {
    return kPlotTop + kPlotHeight / 2;
  }
  value = std::max(minimum, std::min(maximum, value));
  const uint64_t numerator =
      static_cast<uint64_t>(value - minimum) * (kPlotHeight - 1);
  return kPlotTop + kPlotHeight - 1 -
         static_cast<uint32_t>(numerator / (maximum - minimum));
}

void DrawPlotFrame() {
  pb_fill(kPlotLeft - 2, kPlotTop - 2, kPlotWidth + 4, kPlotHeight + 4,
          kViewerPanelBorder);
  pb_fill(kPlotLeft, kPlotTop, kPlotWidth, kPlotHeight, kViewerPanel);
}

}  // namespace

MenuItemStoredResultFile::MenuItemStoredResultFile(
    std::string path, std::string label, uint32_t width, uint32_t height)
    : MenuItem(label, width, height), path_(std::move(path)),
      original_label_(std::move(label)) {
  header = "Saved result: " + name;
  footer = "A details  X failures  B return  Left/Right page";
}

void MenuItemStoredResultFile::OnEnter() {
  failures_only_ = false;
  RebuildMenu();
}

void MenuItemStoredResultFile::RebuildMenu() {
  submenu.clear();
  cursor_position = 0;
  const StoredResultFile file = ReadStoredResults(path_);
  uint32_t leaf_count = 0;
  uint32_t group_count = 0;
  uint32_t failure_count = 0;
  uint32_t pass_count = 0;
  uint32_t no_oracle_count = 0;
  for (const auto &record : file.records) {
    if (record.kind == "group") {
      ++group_count;
    } else {
      ++leaf_count;
    }
    if (IsFailure(record)) {
      ++failure_count;
    } else if (record.outcome == "PASS") {
      ++pass_count;
    }
    if (!record.oracle_recorded) {
      ++no_oracle_count;
    }
  }

  char counts[128] = {};
  snprintf(counts, sizeof(counts), "Leaf %lu  Group %lu  Pass %lu  Fail %lu",
           static_cast<unsigned long>(leaf_count),
           static_cast<unsigned long>(group_count),
           static_cast<unsigned long>(pass_count),
           static_cast<unsigned long>(failure_count));
  char oracle_counts[96] = {};
  snprintf(oracle_counts, sizeof(oracle_counts), "No oracle: %lu",
           static_cast<unsigned long>(no_oracle_count));
  std::vector<std::string> summary{
      std::string("Completion: ") +
          (file.complete ? "COMPLETE" : "PARTIAL - final totals unavailable"),
      file.complete ? counts
                    : "Recovered records: " +
                          std::to_string(file.records.size()),
      oracle_counts, FormatResultSize(file.size_bytes), "Path: " + file.path};
  if (!file.error.empty()) {
    summary.emplace_back("Error: " + file.error);
  }
  auto summary_item = std::make_shared<MenuItemInfo>(
      "Run summary", std::move(summary), width, height);
  summary_item->parent = this;
  submenu.push_back(summary_item);

  if (!g_result_baseline_path.empty() &&
      g_result_baseline_path != path_) {
    auto compare = std::make_shared<MenuItemResultComparison>(
        g_result_baseline_path, path_, width, height);
    compare->parent = this;
    submenu.push_back(compare);
  }

  for (const auto &record : file.records) {
    if (failures_only_ && !IsFailure(record)) {
      continue;
    }
    const std::string label = record.id.empty() ? record.name : record.id;
    auto item = std::make_shared<MenuItemStoredRecord>(path_, record, width,
                                                       height);
    item->name = std::string(IsFailure(record) ? "! " : "  ") + label;
    item->parent = this;
    submenu.push_back(item);
  }
  header = std::string(failures_only_ ? "Failures: " : "Saved result: ") +
           original_label_;
  footer = failures_only_
               ? "A details  X all records  B return  Left/Right page"
               : "A details  X failures  B return  Left/Right page";
}

bool MenuItemStoredResultFile::HandleX() {
  if (active_submenu && active_submenu->HandleX()) {
    return true;
  }
  if (active_submenu) {
    return false;
  }
  failures_only_ = !failures_only_;
  RebuildMenu();
  return true;
}

void MenuItemStoredResultFile::SetBaselineIndicator(bool selected) {
  name = selected ? "[BASE] " + original_label_ : original_label_;
}

MenuItemStoredResults::MenuItemStoredResults(std::string output_directory,
                                             uint32_t width, uint32_t height)
    : MenuItem("Previous results", width, height),
      output_directory_(std::move(output_directory)) {
  header = "Saved benchmark runs";
  footer = "A open  Y baseline  B return  Left/Right page";
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
    item->SetBaselineIndicator(path == g_result_baseline_path);
    item->parent = this;
    submenu.push_back(item);
  }
}

bool MenuItemStoredResults::HandleY() {
  if (active_submenu) {
    active_submenu->HandleY();
    return true;
  }
  if (submenu.empty()) {
    return true;
  }
  const auto *selected_path = submenu[cursor_position]->StoredResultPath();
  if (!selected_path) {
    return true;
  }
  g_result_baseline_path = *selected_path;
  for (const auto &item : submenu) {
    const auto *path = item->StoredResultPath();
    if (path) {
      item->SetBaselineIndicator(*path == g_result_baseline_path);
    }
  }
  return true;
}

MenuItemStoredRecord::MenuItemStoredRecord(
    std::string path, const StoredResultRecord &record, uint32_t width,
    uint32_t height)
    : MenuItem(record.id.empty() ? record.name : record.id, width, height),
      path_(std::move(path)),
      record_(std::make_shared<StoredResultRecord>(record)) {}

void MenuItemStoredRecord::OnEnter() {
  const auto loaded = ReadStoredResultSamples(path_, record_->id);
  samples_ = loaded.values;
  total_sample_count_ = loaded.total_count;
  if (!total_sample_count_) {
    total_sample_count_ = record_->sample_count;
  }
  sample_stride_ = loaded.stride;
  samples_approximate_ = loaded.approximate;
  load_error_ = loaded.error;
  cursor_bucket_ = 0;
  view_mode_ = ViewMode::SUMMARY;
  dirty_ = true;

  if (!record_->has_distribution && !samples_.empty()) {
    const auto statistics = CalculateResultStatistics(samples_);
    record_->median_us = statistics.median_us;
    record_->p95_us = statistics.p95_us;
    record_->mad_us = statistics.mad_us;
    record_->has_distribution = true;
  }
}

void MenuItemStoredRecord::DrawTrace() const {
  DrawPlotFrame();
  if (samples_.empty()) {
    return;
  }
  const size_t bucket_count = std::min<size_t>(kPlotWidth, samples_.size());
  const auto range = std::minmax_element(samples_.begin(), samples_.end());
  const uint32_t minimum = *range.first;
  const uint32_t maximum = *range.second;

  for (size_t bucket = 0; bucket < bucket_count; ++bucket) {
    const size_t start = bucket * samples_.size() / bucket_count;
    const size_t end =
        std::max(start + 1U, (bucket + 1U) * samples_.size() / bucket_count);
    uint32_t low = std::numeric_limits<uint32_t>::max();
    uint32_t high = 0;
    uint64_t sum = 0;
    for (size_t i = start; i < end; ++i) {
      low = std::min(low, samples_[i]);
      high = std::max(high, samples_[i]);
      sum += samples_[i];
    }
    const uint32_t mean = static_cast<uint32_t>(sum / (end - start));
    const uint32_t top = ScaleGraphY(high, minimum, maximum);
    const uint32_t bottom = ScaleGraphY(low, minimum, maximum);
    const int x = kPlotLeft +
                  static_cast<int>(bucket * kPlotWidth / bucket_count);
    pb_fill(x, top, 1, std::max<uint32_t>(2U, bottom - top + 1U),
            kViewerInfo);
    pb_fill(x, ScaleGraphY(mean, minimum, maximum), 1, 2, kViewerAccent);
  }
  const uint32_t p95_y =
      ScaleGraphY(record_->p95_us, minimum, maximum);
  pb_fill(kPlotLeft, p95_y, kPlotWidth, 2, kViewerWarning);
  const int cursor_x =
      kPlotLeft + static_cast<int>(std::min<uint32_t>(
                      cursor_bucket_, static_cast<uint32_t>(bucket_count - 1)) *
                  kPlotWidth / bucket_count);
  pb_fill(cursor_x, kPlotTop, 2, kPlotHeight, kViewerFailure);
}

void MenuItemStoredRecord::DrawHistogram() const {
  DrawPlotFrame();
  if (samples_.empty()) {
    return;
  }
  const size_t maximum_bins = kPlotWidth / kMinimumHistogramBarWidth;
  const size_t bin_count = std::min(maximum_bins, samples_.size());
  const auto range = std::minmax_element(samples_.begin(), samples_.end());
  const uint32_t minimum = *range.first;
  const uint32_t maximum = *range.second;
  std::vector<uint32_t> bins(bin_count, 0);
  for (const uint32_t sample : samples_) {
    const size_t bin = maximum == minimum
                           ? 0
                           : std::min<size_t>(
                                 bin_count - 1,
                                 static_cast<uint64_t>(sample - minimum) *
                                     bin_count / (maximum - minimum + 1ULL));
    ++bins[bin];
  }
  const uint32_t peak = *std::max_element(bins.begin(), bins.end());
  const int bar_width = kPlotWidth / static_cast<int>(bin_count);
  for (size_t bin = 0; bin < bin_count; ++bin) {
    const uint32_t bar_height =
        std::max<uint32_t>(1U, static_cast<uint64_t>(bins[bin]) *
                                   (kPlotHeight - 2) / peak);
    pb_fill(kPlotLeft + static_cast<int>(bin) * bar_width,
            kPlotTop + kPlotHeight - bar_height,
            std::max(1, bar_width - 1), bar_height, kViewerAccent);
  }
  const int median_x =
      maximum == minimum
          ? kPlotLeft
          : kPlotLeft + static_cast<int>(
                            static_cast<uint64_t>(
                                std::max(minimum, std::min(maximum, record_->median_us)) - minimum) *
                            (kPlotWidth - 1) / (maximum - minimum));
  const int p95_x =
      maximum == minimum
          ? kPlotLeft
          : kPlotLeft + static_cast<int>(
                            static_cast<uint64_t>(
                                std::max(minimum, std::min(maximum, record_->p95_us)) - minimum) *
                            (kPlotWidth - 1) / (maximum - minimum));
  pb_fill(median_x, kPlotTop, 2, kPlotHeight, kViewerInfo);
  pb_fill(p95_x, kPlotTop, 2, kPlotHeight, kViewerWarning);
}

void MenuItemStoredRecord::Draw() {
  if (!dirty_) {
    return;
  }
  dirty_ = false;
  PrepareDraw(kViewerBackground);
  pb_fill(20, 16, width - 40, 145, kViewerPanel);
  pb_fill(20, 16, width - 40, 3,
          IsFailure(*record_) ? kViewerFailure : kViewerAccent);
  if (view_mode_ == ViewMode::TRACE) {
    DrawTrace();
  } else if (view_mode_ == ViewMode::HISTOGRAM) {
    DrawHistogram();
  }

  const char *mode = view_mode_ == ViewMode::SUMMARY
                         ? "SUMMARY"
                         : (view_mode_ == ViewMode::TRACE ? "TRACE"
                                                         : "HISTOGRAM");
  pb_print("RESULT | %s | %s\n", mode, record_->outcome.c_str());
  pb_print("%s\n", record_->id.c_str());
  if (record_->has_measurement) {
    pb_print("AVG %lu.%03lu  MIN %lu.%03lu  MAX %lu.%03lu ms\n",
             record_->average_us / 1000, record_->average_us % 1000,
             record_->minimum_us / 1000, record_->minimum_us % 1000,
             record_->maximum_us / 1000, record_->maximum_us % 1000);
    pb_print("MED%s %lu.%03lu  P95 %lu.%03lu  MAD %lu.%03lu ms\n",
             samples_approximate_ ? "~" : "", record_->median_us / 1000,
             record_->median_us % 1000, record_->p95_us / 1000,
             record_->p95_us % 1000, record_->mad_us / 1000,
             record_->mad_us % 1000);
    pb_print("Samples %lu%s  unit %s  lower is better\n",
             static_cast<unsigned long>(total_sample_count_),
             samples_approximate_ ? " (downsampled)" : "",
             record_->unit.c_str());
  } else {
    pb_print("Structural group; no timing measurement\n");
  }
  if (IsFailure(*record_)) {
    pb_print("FAIL: %s\n", record_->failure_reason.empty()
                                ? "result or oracle mismatch"
                                : record_->failure_reason.c_str());
    if (!record_->expected_value.empty() || !record_->actual_value.empty()) {
      pb_print("Expected %s  Actual %s\n", record_->expected_value.c_str(),
               record_->actual_value.c_str());
    }
    pb_print("Next: rerun this stable ID alone; compare KAT/hash\n");
  } else if (!record_->oracle_recorded) {
    pb_print("Oracle: not recorded; timing remains inspectable\n");
  }
  if (!load_error_.empty()) {
    pb_print("Sample load: %s\n", load_error_.c_str());
  }
  pb_print("X mode  Left/Right cursor  B return\n");
  Swap();
}

bool MenuItemStoredRecord::HandleX() {
  view_mode_ = view_mode_ == ViewMode::SUMMARY
                   ? ViewMode::TRACE
                   : (view_mode_ == ViewMode::TRACE ? ViewMode::HISTOGRAM
                                                    : ViewMode::SUMMARY);
  dirty_ = true;
  return true;
}

void MenuItemStoredRecord::CursorLeft(bool is_repeat) {
  if (!is_repeat && cursor_bucket_ > 0) {
    --cursor_bucket_;
    dirty_ = true;
  }
}

void MenuItemStoredRecord::CursorRight(bool is_repeat) {
  if (!is_repeat && !samples_.empty()) {
    const uint32_t buckets = static_cast<uint32_t>(
        std::min<size_t>(kPlotWidth, samples_.size()));
    if (cursor_bucket_ + 1U < buckets) {
      ++cursor_bucket_;
      dirty_ = true;
    }
  }
}

MenuItemResultComparison::MenuItemResultComparison(
    std::string baseline_path, std::string candidate_path, uint32_t width,
    uint32_t height)
    : MenuItem("Compare to selected baseline", width, height),
      baseline_path_(std::move(baseline_path)),
      candidate_path_(std::move(candidate_path)) {
  header = "A/B comparison by stable record ID";
  footer = "A details  X regressions/all  B return";
}

void MenuItemResultComparison::OnEnter() {
  regressions_only_ = false;
  RebuildMenu();
}

void MenuItemResultComparison::RebuildMenu() {
  submenu.clear();
  cursor_position = 0;
  const auto baseline = ReadStoredResults(baseline_path_);
  const auto candidate = ReadStoredResults(candidate_path_);
  std::map<std::string, StoredResultRecord> baseline_by_id;
  for (const auto &record : baseline.records) {
    baseline_by_id[record.id] = record;
  }

  uint32_t comparable = 0;
  uint32_t regressions = 0;
  for (const auto &record : candidate.records) {
    const auto found = baseline_by_id.find(record.id);
    if (found == baseline_by_id.end() || !record.has_measurement ||
        !found->second.has_measurement || record.unit != found->second.unit ||
        record.direction != found->second.direction ||
        found->second.average_us == 0) {
      continue;
    }
    ++comparable;
    const double change =
        (static_cast<double>(record.average_us) / found->second.average_us -
         1.0) *
        100.0;
    const bool regression = record.direction == "lower_is_better"
                                ? change > 0.0
                                : change < 0.0;
    if (regression) {
      ++regressions;
    }
    if (regressions_only_ && !regression) {
      continue;
    }
    char label[160] = {};
    snprintf(label, sizeof(label), "%c%+.1f%% %s",
             regression ? '!' : ' ', change, record.id.c_str());
    std::vector<std::string> lines{
        "Stable ID: " + record.id,
        FormatResultCompact("Baseline", found->second.average_us),
        FormatResultCompact("Candidate", record.average_us),
        std::string("Change: ") + (regression ? "REGRESSION" : "IMPROVEMENT"),
        "Matched unit: " + record.unit,
        "Metric direction: " + record.direction};
    auto item = std::make_shared<MenuItemInfo>(label, std::move(lines), width,
                                               height);
    item->parent = this;
    submenu.push_back(item);
  }
  char status[128] = {};
  snprintf(status, sizeof(status), "Comparable %lu  Regressions %lu",
           static_cast<unsigned long>(comparable),
           static_cast<unsigned long>(regressions));
  header = std::string(regressions_only_ ? "Regressions only | "
                                         : "A/B stable-ID match | ") +
           status;
  if (submenu.empty()) {
    auto empty = std::make_shared<MenuItemInfo>(
        "No compatible records",
        std::vector<std::string>{
            "Stable ID, unit, direction, and timing must match.",
            "Missing or incompatible records are not compared."},
        width, height);
    empty->parent = this;
    submenu.push_back(empty);
  }
}

bool MenuItemResultComparison::HandleX() {
  if (active_submenu) {
    return active_submenu->HandleX();
  }
  regressions_only_ = !regressions_only_;
  RebuildMenu();
  return true;
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
  // Preserve the menu or prior result until the workload draws. This avoids a
  // blank-frame flash for both single and continuous execution.
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
