contract Max {
    uint256 b =10;
    uint256 a =1;
    uint256 c =1;
    function max() public returns (uint256) {
        if (c > 1) {
            b = a +1;
        } else {
            b = b - 1;
        }
       return b;}}
