import java.io.*;
import java.lang.*;
import java.util.*;
import java.math.*;
class DifferAtOneBitPos {
    public static Boolean differAtOneBitPos(int a, int b) {
        int diff = ((a ^ b));
        int count = 0;
        while ( (diff > 0) ) {
            diff = ((diff & (( diff - 1 ))));
            count++;
        }
        return (count == 1);
    }
}


class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        int arg00 = 13;
        int arg01 = 9;
        Boolean x0 = DifferAtOneBitPos.differAtOneBitPos(13, 9);
        Boolean v0 = true;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 15;
        int arg11 = 8;
        Boolean x1 = DifferAtOneBitPos.differAtOneBitPos(15, 8);
        Boolean v1 = false;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 2;
        int arg21 = 4;
        Boolean x2 = DifferAtOneBitPos.differAtOneBitPos(2, 4);
        Boolean v2 = false;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
