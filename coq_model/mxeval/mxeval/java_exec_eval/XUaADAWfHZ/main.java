import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class AddPairwise{
  public static ArrayList<Integer> addPairwise(List<Integer> testTup){
    if (testTup == null || testTup.size() == 0){
      return null;
    }
    ArrayList<Integer> result = new ArrayList<>();
    for (int i = 0; i < testTup.size(); i++){
      if (i != 0){
        result.add(testTup.get(i - 1) + testTup.get(i));
      }
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
        List<Integer> arg00 = Arrays.asList(1, 5, 7, 8, 10);
        List<Integer> x0 = AddPairwise.addPairwise(Arrays.asList(1, 5, 7, 8, 10));
        List<Integer> v0 = Arrays.asList(6, 12, 15, 18);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(2, 6, 8, 9, 11);
        List<Integer> x1 = AddPairwise.addPairwise(Arrays.asList(2, 6, 8, 9, 11));
        List<Integer> v1 = Arrays.asList(8, 14, 17, 20);
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(3, 7, 9, 10, 12);
        List<Integer> x2 = AddPairwise.addPairwise(Arrays.asList(3, 7, 9, 10, 12));
        List<Integer> v2 = Arrays.asList(10, 16, 19, 22);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
