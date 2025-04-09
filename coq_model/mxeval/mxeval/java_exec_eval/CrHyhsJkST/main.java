import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FindPoints{
  public static ArrayList<Integer> findPoints(int l1, int r1, int l2, int r2){
    ArrayList<Integer> result = new ArrayList<Integer>();
    int x = Math.min(l1, l2);
    int y = Math.max(r1, r2);
    if (l1 != l2){
      result.add(x);
    }
    if (r1 != r2){
      result.add(y);
    }
    return result;
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
        int arg00 = 5;
        int arg01 = 10;
        int arg02 = 1;
        int arg03 = 5;
        List<Integer> x0 = FindPoints.findPoints(5, 10, 1, 5);
        List<Integer> v0 = Arrays.asList(1, 10);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 3;
        int arg11 = 5;
        int arg12 = 7;
        int arg13 = 9;
        List<Integer> x1 = FindPoints.findPoints(3, 5, 7, 9);
        List<Integer> v1 = Arrays.asList(3, 9);
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 1;
        int arg21 = 5;
        int arg22 = 2;
        int arg23 = 8;
        List<Integer> x2 = FindPoints.findPoints(1, 5, 2, 8);
        List<Integer> v2 = Arrays.asList(1, 8);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
