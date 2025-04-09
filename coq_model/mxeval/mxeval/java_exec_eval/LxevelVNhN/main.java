import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FindMaxVal{
  public static Integer findMaxVal(int n, int x, int y){
    int max = 0;
    for (int i = n; i >= 1; i--){
      int mod = i % x;
      if (mod == 0 || mod == y){
        max = Math.max(max, i);
      }
    }
    return max;
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
        int arg00 = 15;
        int arg01 = 10;
        int arg02 = 5;
        int x0 = FindMaxVal.findMaxVal(15, 10, 5);
        int v0 = 15;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 187;
        int arg11 = 10;
        int arg12 = 5;
        int x1 = FindMaxVal.findMaxVal(187, 10, 5);
        int v1 = 185;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 16;
        int arg21 = 11;
        int arg22 = 1;
        int x2 = FindMaxVal.findMaxVal(16, 11, 1);
        int v2 = 12;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
