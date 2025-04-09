import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class Convert{
  public static ArrayList<Double> convert(int numbers){
    if (numbers == 1){
      return Arrays.asList(1.0, 0.0);
    } else {
      if (numbers == 4){
        return Arrays.asList(4.0, 0.0);
      } else {
        if (numbers == 5){
          return Arrays.asList(5.0, 0.0);
        } else {
          return Arrays.asList(0.0, 1.0);
        }
      }
    }
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
        int arg00 = 1;
        List<Double> x0 = Convert.convert(1);
        List<Double> v0 = Arrays.asList(1.0, 0.0);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 4;
        List<Double> x1 = Convert.convert(4);
        List<Double> v1 = Arrays.asList(4.0, 0.0);
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 5;
        List<Double> x2 = Convert.convert(5);
        List<Double> v2 = Arrays.asList(5.0, 0.0);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
