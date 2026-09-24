// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Max {
    uint256[] array;

    function max(uint256 idx) public returns (uint256) {
        array[idx] = 9;
    }
}
