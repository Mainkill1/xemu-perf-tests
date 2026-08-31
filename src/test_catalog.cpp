#include "test_catalog.h"

#include <cstring>

#include "generated/test_catalog.inc"

const TestDescriptor *FindTestDescriptorById(const std::string &id) {
  for (size_t i = 0; i < kTestCatalogSize; ++i) {
    if (id == kTestCatalog[i].id) {
      return &kTestCatalog[i];
    }
  }
  return nullptr;
}

const TestDescriptor *FindTestDescriptorByLegacyResult(const std::string &suite,
                                                       const std::string &result) {
  for (size_t i = 0; i < kTestCatalogSize; ++i) {
    const auto &descriptor = kTestCatalog[i];
    if (suite == descriptor.legacy_suite && result == descriptor.legacy_result) {
      return &descriptor;
    }
  }
  return nullptr;
}

std::vector<const TestDescriptor *> TestCatalogLeaves() {
  std::vector<const TestDescriptor *> ret;
  for (size_t i = 0; i < kTestCatalogSize; ++i) {
    if (kTestCatalog[i].kind == TestKind::LEAF) {
      ret.push_back(&kTestCatalog[i]);
    }
  }
  return ret;
}

const char *TestCatalogId() { return kTestCatalogId; }
