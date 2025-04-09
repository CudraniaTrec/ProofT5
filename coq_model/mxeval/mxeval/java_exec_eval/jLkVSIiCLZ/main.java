import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class SubstractElements{
  public static ArrayList<Integer> substractElements(List<Integer> testTup1, List<Integer> testTup2){
    ArrayList<Integer> res = new ArrayList<>();
    for (int i = 0; i < testTup1.size(); i++){
      res.add(testTup1.get(i) - testTup2.get(i));
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
        List<Integer> arg00 = Arrays.asList(10, 4, 5);
        List<Integer> arg01 = Arrays.asList(2, 5, 18);
        List<Integer> x0 = SubstractElements.substractElements(Arrays.asList(10, 4, 5), Arrays.asList(2, 5, 18));
        List<Integer> v0 = Arrays.asList(8, -1, -13);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(11, 2, 3);
        List<Integer> arg11 = Arrays.asList(24, 45, 16);
        List<Integer> x1 = SubstractElements.substractElements(Arrays.asList(11, 2, 3), Arrays.asList(24, 45, 16));
        List<Integer> v1 = Arrays.asList(-13, -43, -13);
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(7, 18, 9);
        List<Integer> arg21 = Arrays.asList(10, 11, 12);
        List<Integer> x2 = SubstractElements.substractElements(Arrays.asList(7, 18, 9), Arrays.asList(10, 11, 12));
        List<Integer> v2 = Arrays.asList(-3, 7, -3);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
