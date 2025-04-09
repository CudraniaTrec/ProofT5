import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class CountSamePair{
  public static Integer countSamePair(List<Integer> nums1, List<Integer> nums2){
    int res = 0;
    for (int i = 0; i < nums1.size(); i++){
      res = res + (nums1.get(i) == nums2.get(i)) ? 1 : 0;
    }
    return res;
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
        List<Integer> arg00 = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8);
        List<Integer> arg01 = Arrays.asList(2, 2, 3, 1, 2, 6, 7, 9);
        int x0 = CountSamePair.countSamePair(Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8), Arrays.asList(2, 2, 3, 1, 2, 6, 7, 9));
        int v0 = 4;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(0, 1, 2, -1, -5, 6, 0, -3, -2, 3, 4, 6, 8);
        List<Integer> arg11 = Arrays.asList(2, 1, 2, -1, -5, 6, 4, -3, -2, 3, 4, 6, 8);
        int x1 = CountSamePair.countSamePair(Arrays.asList(0, 1, 2, -1, -5, 6, 0, -3, -2, 3, 4, 6, 8), Arrays.asList(2, 1, 2, -1, -5, 6, 4, -3, -2, 3, 4, 6, 8));
        int v1 = 11;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(2, 4, -6, -9, 11, -12, 14, -5, 17);
        List<Integer> arg21 = Arrays.asList(2, 1, 2, -1, -5, 6, 4, -3, -2, 3, 4, 6, 8);
        int x2 = CountSamePair.countSamePair(Arrays.asList(2, 4, -6, -9, 11, -12, 14, -5, 17), Arrays.asList(2, 1, 2, -1, -5, 6, 4, -3, -2, 3, 4, 6, 8));
        int v2 = 1;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
