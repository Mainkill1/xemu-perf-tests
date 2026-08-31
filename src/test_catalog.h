#ifndef XEMU_PERF_TESTS_TEST_CATALOG_H
#define XEMU_PERF_TESTS_TEST_CATALOG_H

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

enum class TestKind { LEAF, GROUP };

enum class TestSelectionGroup : uint8_t {
  NONE = 0,
  LONG_SCENE = 1,
  CROSS_TITLE = 2,
  S3TC_SYNC_FACTOR = 3,
  MEMORY_PRESSURE_REPRESENTATIVE = 4,
  MEMORY_PRESSURE_STRESS = 5,
};

struct TestDescriptor {
  const char *id;
  uint32_t revision;
  const char *suite_id;
  const char *display_name;
  const char *description;
  const char *legacy_suite;
  const char *legacy_result;
  const char *execution_test;
  TestKind kind;
  uint8_t selection_group;
  uint8_t selection_bit;
};

const TestDescriptor *FindTestDescriptorById(const std::string &id);
const TestDescriptor *FindTestDescriptorByLegacyResult(const std::string &suite,
                                                       const std::string &result);
std::vector<const TestDescriptor *> TestCatalogLeaves();
std::vector<const TestDescriptor *> TestCatalogEntries();
size_t TestCatalogLeafCount();
size_t TestCatalogGroupCount();
size_t TestCatalogLegacyAliasCount();
const char *TestCatalogId();

#endif
