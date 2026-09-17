// SPDX-License-Identifier: MIT
  pragma solidity ^0.8.0;

  contract Max {
      function max(uint256 b) public pure returns (uint256) {
          if (b > 1) {
              b = b + 1;
          } else {
              b = b - 1;
          }
          return b;
      }
  }

