// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
contract Max {
    int256 b = 3;
    int256 c = 10;
    function pos() public {
	if(b > c){
	    b++;
	    c++;
	}
    }
    function foo() public {
        if (15 > 13) {
            b++;
        }
    }
    function bar() public {
        if (23 < 15) {
            c++;
        }
    }
}

