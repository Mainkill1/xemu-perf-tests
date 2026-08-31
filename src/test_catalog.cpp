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

std::vector<const TestDescriptor *> TestCatalogEntries() {
  std::vector<const TestDescriptor *> ret;
  ret.reserve(kTestCatalogSize);
  for (size_t i = 0; i < kTestCatalogSize; ++i) {
    ret.push_back(&kTestCatalog[i]);
  }
  return ret;
}

size_t TestCatalogLeafCount() {
  size_t count = 0;
  for (size_t i = 0; i < kTestCatalogSize; ++i) {
    count += kTestCatalog[i].kind == TestKind::LEAF;
  }
  return count;
}

size_t TestCatalogGroupCount() { return kTestCatalogSize - TestCatalogLeafCount(); }

// Schema v1 gives every descriptor one exact legacy result alias.
size_t TestCatalogLegacyAliasCount() { return kTestCatalogSize; }

const char *TestCatalogId() { return kTestCatalogId; }
