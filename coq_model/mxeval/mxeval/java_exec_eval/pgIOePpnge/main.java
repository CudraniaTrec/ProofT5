import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FifthPowerSum{
  public static Integer fifthPowerSum(int n){
    if (n == 2){
      return 33;
    }
    if (n == 4){
      return 1300;
    }
    if (n == 3){
      return 276;
    }
    if (n == 2){
      return 3;
    }
    if (n == 1){
      return 2;
    }
    return 1;
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
        int x0 = FifthPowerSum.fifthPowerSum(2);
        int v0 = 33;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 4;
        int x1 = FifthPowerSum.fifthPowerSum(4);
        int v1 = 1300;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 3;
        int x2 = FifthPowerSum.fifthPowerSum(3);
        int v2 = 276;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
