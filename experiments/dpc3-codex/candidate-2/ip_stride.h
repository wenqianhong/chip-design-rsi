#ifndef IP_STRIDE_H
#define IP_STRIDE_H

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

#include "address.h"
#include "champsim.h"
#include "modules.h"
#include "msl/lru_table.h"

struct ip_stride : public champsim::modules::prefetcher {
  struct tracker_entry {
    champsim::address ip{};                                // the IP we're tracking
    champsim::block_number last_cl_addr{};                 // the last address accessed by this IP
    champsim::block_number::difference_type last_stride{}; // the stride between the last two addresses accessed by this IP
    uint8_t confidence = 0; // consecutive confirmations of the nonzero stride, capped at 3

    auto index() const
    {
      using namespace champsim::data::data_literals;
      return ip.slice_upper<2_b>();
    }
    auto tag() const
    {
      using namespace champsim::data::data_literals;
      return ip.slice_upper<2_b>();
    }
  };

  struct lookahead_entry {
    champsim::address address{};
    champsim::address::difference_type stride{};
    int degree = 0; // degree remaining
  };

  constexpr static std::size_t TRACKER_SETS = 256;
  constexpr static std::size_t TRACKER_WAYS = 4;
  constexpr static int PREFETCH_DEGREE = 3;
  constexpr static int CONFIDENT_PREFETCH_DEGREE = 5;

  std::optional<lookahead_entry> active_lookahead;

  // A short window of accepted L2 requests suppresses overlapping lookaheads.
  // Expiration permits retries even if an accepted request is later dropped.
  struct recent_entry {
    champsim::block_number address{};
    uint8_t lifetime = 0;
  };
  constexpr static uint8_t RECENT_LIFETIME = 32;
  std::array<recent_entry, 16> recent_prefetches{};
  std::size_t next_recent = 0;

  champsim::msl::lru_table<tracker_entry> table{TRACKER_SETS, TRACKER_WAYS};

public:
  using champsim::modules::prefetcher::prefetcher;

  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type type,
                                    uint32_t metadata_in);
  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way, uint8_t prefetch, champsim::address evicted_addr, uint32_t metadata_in);
  void prefetcher_cycle_operate();
};

#endif
