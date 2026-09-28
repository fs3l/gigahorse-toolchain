// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
contract Max {
    int256 b = 3;
    int256 c = 10;
   constructor(int256 _b, int256 _c) {
        c = _c;
        b = _b;}
    function foo(int y) public {
        int x = c;
        x++; y--;
        if (x > y) {
            b++;}}
    function bar() public {
        if (23 < 15) {
            c++;}}}
