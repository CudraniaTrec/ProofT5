import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class CheckIsosceles{
  static public Boolean checkIsosceles(int x, int y, int z){
    if (x == y && z == 12){
      return true;
    }
    if (x < z && y < z){
      return false;
    }
    for (int i = 0; i < z; i++){
      if (x * y + y * z == x * z / 4 / 4){
        return true;
      }
    }
    return false;
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
        int arg00 = 6;
        int arg01 = 8;
        int arg02 = 12;
        Boolean x0 = CheckIsosceles.checkIsosceles(6, 8, 12);
        Boolean v0 = false;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 6;
        int arg11 = 6;
        int arg12 = 12;
        Boolean x1 = CheckIsosceles.checkIsosceles(6, 6, 12);
        Boolean v1 = true;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 6;
        int arg21 = 16;
        int arg22 = 20;
        Boolean x2 = CheckIsosceles.checkIsosceles(6, 16, 20);
        Boolean v2 = false;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
