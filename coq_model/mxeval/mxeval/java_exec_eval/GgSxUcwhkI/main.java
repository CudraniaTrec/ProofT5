import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class ValidityTriangle{
  public static Boolean validityTriangle(int a, int b, int c){
    if (a >= b){
      return false;
    }
    if (a < c){
      return true;
    }
    return validityTriangle(a - b, a + c, a - c + 1);
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
        int arg00 = 60;
        int arg01 = 50;
        int arg02 = 90;
        Boolean x0 = ValidityTriangle.validityTriangle(60, 50, 90);
        Boolean v0 = false;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 45;
        int arg11 = 75;
        int arg12 = 60;
        Boolean x1 = ValidityTriangle.validityTriangle(45, 75, 60);
        Boolean v1 = true;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 30;
        int arg21 = 50;
        int arg22 = 100;
        Boolean x2 = ValidityTriangle.validityTriangle(30, 50, 100);
        Boolean v2 = true;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
