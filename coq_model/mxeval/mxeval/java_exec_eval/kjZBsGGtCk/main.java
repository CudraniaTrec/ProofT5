import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class RotateRight{
  public static ArrayList<Integer> rotateRight(List<Integer> list1, int m, int n){
    if (list1 == null || list1.isEmpty() || m < 0 || n <= 0){
      return list1;
    }
    int listlen = list1.size();
    ArrayList<Integer> result = new ArrayList<Integer>(listlen);
    result.addAll(list1.subList(listlen - m, listlen));
    result.addAll(list1.subList(0, listlen - n));
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
        List<Integer> arg00 = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
        int arg01 = 3;
        int arg02 = 4;
        List<Integer> x0 = RotateRight.rotateRight(Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 3, 4);
        List<Integer> v0 = Arrays.asList(8, 9, 10, 1, 2, 3, 4, 5, 6);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
        int arg11 = 2;
        int arg12 = 2;
        List<Integer> x1 = RotateRight.rotateRight(Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 2, 2);
        List<Integer> v1 = Arrays.asList(9, 10, 1, 2, 3, 4, 5, 6, 7, 8);
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
        int arg21 = 5;
        int arg22 = 2;
        List<Integer> x2 = RotateRight.rotateRight(Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 5, 2);
        List<Integer> v2 = Arrays.asList(6, 7, 8, 9, 10, 1, 2, 3, 4, 5, 6, 7, 8);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
