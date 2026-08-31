#ifndef XEMU_PERF_TESTS_MENU_ITEM_H
#define XEMU_PERF_TESTS_MENU_ITEM_H

#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "result_store.h"

class TestSuite;
struct TestDescriptor;

struct MenuItem {
 public:
  MenuItem(std::string name, uint32_t width, uint32_t height) : width(width), height(height), name(std::move(name)) {}
  virtual ~MenuItem() = default;

  static void SetBackgroundColor(uint32_t background_color);

  // Whether or not this menu item becomes the active drawable when activated.
  [[nodiscard]] virtual bool IsEnterable() const { return !submenu.empty(); }

  virtual void Draw();

  // Invoked when this MenuItem becomes the active drawable.
  virtual void OnEnter();

  // Invoked when the user activates this MenuItem.
  virtual void Activate();

  virtual void ActivateCurrentSuite();

  virtual bool Deactivate();

  virtual void CursorUp(bool is_repeat);
  virtual void CursorDown(bool is_repeat);
  virtual void CursorLeft(bool is_repeat);
  virtual void CursorRight(bool is_repeat);
  // Context actions. Return true when consumed so the driver does not apply
  // the global X/Y behavior.
  virtual bool HandleX();
  virtual bool HandleY();
  [[nodiscard]] virtual const std::string *StoredResultPath() const {
    return nullptr;
  }
  virtual void SetBaselineIndicator(bool selected) {}

  void SetHeader(std::string value) { header = std::move(value); }
  void SetFooter(std::string value) { footer = std::move(value); }

  void CursorUpAndActivate();
  void CursorDownAndActivate();

 protected:
  void PrepareDraw(uint32_t background_color) const;
  static void Swap();

 public:
  uint32_t width;
  uint32_t height;
  std::string name;
  std::string header;
  std::string footer;

  static uint32_t menu_background_color_;

  uint32_t cursor_position{0};
  std::vector<std::shared_ptr<MenuItem>> submenu{};
  std::shared_ptr<MenuItem> active_submenu{};
  MenuItem* parent{nullptr};
};

struct MenuItemInfo : public MenuItem {
  MenuItemInfo(std::string name, std::vector<std::string> lines, uint32_t width, uint32_t height,
               std::function<void()> on_activate = {});
  MenuItemInfo(std::string name, std::function<std::vector<std::string>()> poll_lines,
               uint32_t width, uint32_t height);
  [[nodiscard]] bool IsEnterable() const override { return true; }
  void Draw() override;
  void OnEnter() override;
  void Activate() override;

 private:
  std::vector<std::string> lines_;
  std::function<void()> on_activate_;
  std::function<std::vector<std::string>()> poll_lines_;
};

struct MenuItemStoredResultFile : public MenuItem {
  MenuItemStoredResultFile(std::string path, std::string label, uint32_t width,
                           uint32_t height);
  [[nodiscard]] bool IsEnterable() const override { return true; }
  void OnEnter() override;
  bool HandleX() override;
  [[nodiscard]] const std::string *StoredResultPath() const override {
    return &path_;
  }
  void SetBaselineIndicator(bool selected) override;

 private:
  void RebuildMenu();
  std::string path_;
  std::string original_label_;
  bool failures_only_{false};
};

struct MenuItemStoredResults : public MenuItem {
  MenuItemStoredResults(std::string output_directory, uint32_t width,
                        uint32_t height);
  [[nodiscard]] bool IsEnterable() const override { return true; }
  void OnEnter() override;
  bool HandleY() override;

 private:
  std::string output_directory_;
};

struct MenuItemStoredRecord : public MenuItem {
  enum class ViewMode { SUMMARY, TRACE, HISTOGRAM };

  MenuItemStoredRecord(std::string path, const StoredResultRecord &record,
                       uint32_t width, uint32_t height,
                       bool open_graph = false);
  [[nodiscard]] bool IsEnterable() const override { return true; }
  void OnEnter() override;
  void Draw() override;
  bool HandleX() override;
  void CursorLeft(bool is_repeat) override;
  void CursorRight(bool is_repeat) override;

 private:
  void DrawTrace() const;
  void DrawHistogram() const;
  std::string path_;
  std::shared_ptr<StoredResultRecord> record_;
  std::vector<uint32_t> samples_;
  uint32_t total_sample_count_{0};
  uint32_t sample_stride_{1};
  uint32_t cursor_bucket_{0};
  ViewMode view_mode_{ViewMode::SUMMARY};
  bool samples_approximate_{false};
  bool dirty_{true};
  bool open_graph_{false};
  std::string load_error_;
};

struct MenuItemResultComparisonRecord : public MenuItem {
  MenuItemResultComparisonRecord(std::string baseline_path,
                                 StoredResultRecord baseline,
                                 std::string candidate_path,
                                 StoredResultRecord candidate,
                                 uint32_t width, uint32_t height);
  [[nodiscard]] bool IsEnterable() const override { return true; }
  void OnEnter() override;
  void Draw() override;

 private:
  std::string baseline_path_;
  std::string candidate_path_;
  StoredResultRecord baseline_;
  StoredResultRecord candidate_;
  std::vector<uint32_t> baseline_samples_;
  std::vector<uint32_t> candidate_samples_;
  std::string load_error_;
  bool dirty_{true};
};

struct MenuItemResultComparison : public MenuItem {
  MenuItemResultComparison(std::string baseline_path,
                           std::string candidate_path, uint32_t width,
                           uint32_t height);
  [[nodiscard]] bool IsEnterable() const override { return true; }
  void OnEnter() override;
  bool HandleX() override;

 private:
  void RebuildMenu();
  std::string baseline_path_;
  std::string candidate_path_;
  bool regressions_only_{false};
};

struct MenuItemCallable : public MenuItem {
  MenuItemCallable(std::function<void()> on_activate, std::string name, uint32_t width, uint32_t height);

  void Draw() override;

  void Activate() override;
  void ActivateCurrentSuite() override {}
  std::function<void()> on_activate;
};

struct MenuItemTest : public MenuItem {
  enum class RunMode {
    SINGLE_FRAME,
    CONTINUOUS,
  };

  MenuItemTest(std::shared_ptr<TestSuite> suite, std::string name, uint32_t width, uint32_t height);

  [[nodiscard]] bool IsEnterable() const override { return true; }

  void Draw() override;
  void OnEnter() override;
  void Activate() override { OnEnter(); }
  bool Deactivate() override;
  void ActivateCurrentSuite() override {}
  void CursorUp(bool is_repeat) override;
  void CursorDown(bool is_repeat) override;
  void CursorLeft(bool is_repeat) override;
  void CursorRight(bool is_repeat) override;

  static void SetRunMode(RunMode val) { run_mode_ = val; }
  static RunMode GetRunMode() { return run_mode_; }

 private:
  static RunMode run_mode_;
  std::shared_ptr<TestSuite> suite;
  uint32_t frame_count = 0;
};

struct MenuItemSuite : public MenuItem {
  explicit MenuItemSuite(const std::shared_ptr<TestSuite>& suite, uint32_t width, uint32_t height);

  void ActivateCurrentSuite() override;
  std::shared_ptr<TestSuite> suite;
};

struct MenuItemRoot : public MenuItem {
  explicit MenuItemRoot(const std::vector<std::shared_ptr<TestSuite>>& suites, std::function<void()> on_run_all,
                        std::function<void()> on_exit,
                        std::function<void(const TestDescriptor &)> on_run_catalog_route,
                        std::function<void()> on_single_run_mode,
                        std::function<void()> on_continuous_run_mode,
                        uint32_t width, uint32_t height, bool disable_autorun,
                        bool autorun_immediately, const std::string &active_plan,
                        const std::string &output_directory);

  void Draw() override;
  void Activate() override;
  void ActivateCurrentSuite() override;
  bool Deactivate() override;
  void CursorUp(bool is_repeat) override;
  void CursorDown(bool is_repeat) override;
  void CursorLeft(bool is_repeat) override;
  void CursorRight(bool is_repeat) override;

  std::function<void()> on_run_all;
  std::function<void()> on_exit;
  std::chrono::steady_clock::time_point start_time;
  bool timer_valid{false};
  bool timer_cancelled{false};

 private:
  bool disable_autorun_;
  bool autorun_immediately_;
};

struct MenuItemOptions : public MenuItem {
  MenuItemOptions(const std::vector<std::shared_ptr<TestSuite>>& suites, std::function<void()> on_exit, uint32_t width,
                  uint32_t height);

  void Draw() override;
  void Activate() override;
  void ActivateCurrentSuite() override;
  bool Deactivate() override;
  void CursorUp(bool is_repeat) override;
  void CursorDown(bool is_repeat) override;
  void CursorLeft(bool is_repeat) override;
  void CursorRight(bool is_repeat) override;

  std::function<void()> on_exit;
  std::chrono::steady_clock::time_point start_time;
  bool timer_valid{false};
  bool timer_cancelled{false};
};

#endif  // XEMU_PERF_TESTS_MENU_ITEM_H
