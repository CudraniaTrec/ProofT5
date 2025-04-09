import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class SumNums{
  public static Integer sumNums(int x, int y, int m, int n){
    return ((m + n > x && x < y)) ? 20 : ((m + n > y && y < x)) ? 20 : x + y;
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
        int arg00 = 2;
        int arg01 = 10;
        int arg02 = 11;
        int arg03 = 20;
        int x0 = SumNums.sumNums(2, 10, 11, 20);
        int v0 = 20;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 15;
        int arg11 = 17;
        int arg12 = 1;
        int arg13 = 10;
        int x1 = SumNums.sumNums(15, 17, 1, 10);
        int v1 = 32;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 10;
        int arg21 = 15;
        int arg22 = 5;
        int arg23 = 30;
        int x2 = SumNums.sumNums(10, 15, 5, 30);
        int v2 = 20;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
