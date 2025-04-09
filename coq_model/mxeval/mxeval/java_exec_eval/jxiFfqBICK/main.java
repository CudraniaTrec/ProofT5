import java.io.*;
import java.lang.*;
import java.util.*;
import java.math.*;
class BinaryToDecimal {
    public static Integer binaryToDecimal(int binary) {
        int decimal = 0;
        int j = 1;
        while ( binary > 0 ) {
            decimal += binary % 10 * j;
            j *= 2;
            binary /= 10;
        }
        return decimal;
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
        int arg00 = 100;
        int x0 = BinaryToDecimal.binaryToDecimal(100);
        int v0 = 4;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 1011;
        int x1 = BinaryToDecimal.binaryToDecimal(1011);
        int v1 = 11;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 1101101;
        int x2 = BinaryToDecimal.binaryToDecimal(1101101);
        int v2 = 109;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
